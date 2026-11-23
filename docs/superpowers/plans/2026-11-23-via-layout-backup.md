# Keep VIA edits across flashes: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `tools/flash-pad.sh` backs up the pad's VIA layout before flashing and puts Rahul's edits back on top of the new build's defaults afterwards.

**Architecture:**
- **Pure merge logic:** `tools/via_merge.py`, with no I/O.
- **The tool around it:** `tools/via-layout.py` handles the HID talk, the JSON files and the commands. It batches all VIA commands into single `hidapitester.exe` calls.
- **`flash-pad.sh`** calls `backup` before rebooting the pad and `restore` after the build is confirmed.

**Tech stack:** Python 3 (standard library only, `unittest`), bash, `hidapitester.exe` over WSL interop.

**Spec:** `docs/superpowers/specs/2026-11-23-via-layout-backup-design.md`

## Global constraints

- No firmware change.
- **VIA command IDs:** `0x05` set keycode, `0x06` keymap reset, `0x0D` macro buffer size, `0x0E`/`0x0F` macro get/set, `0x11` layer count, `0x12` keymap get buffer, `0x14`/`0x15` encoder get/set.
- **Report format:** 32-byte reports, sent with a leading `0` report ID and `--length 33`. Buffer chunks are at most 28 bytes, and each reply echoes the command byte in byte 0.
- **KB16 shape:** 4 rows × 5 cols, 3 encoders. The layer count and macro buffer size are read from the pad.
- **Files:** `via/layout.json` and `via/defaults.json`, each carrying the build ID (`F0 01`) it was read from.
- **Recovery:** if the backup fails, nothing is flashed; `--skip-layout` overrides that.

## Plan-time findings (beyond the spec)

- **The full VIA reset `0x0A` is compiled out** (`VIA_EEPROM_ALLOW_RESET`). Keymap reset `0x06` resets both keys and knob turns to the build's defaults, so `restore` always sends `0x06` before reading the defaults.
- **QMK's wipe check uses only the build day.** Same-day rebuilds keep the old layout, and their new `keymap.c` defaults never load. Always resetting with `0x06` makes restore correct in both cases, so the spec's "same build ID: do nothing" special case is dropped: the merge handles it.
- **A rerun of `restore` after a success must not undo it.** So after a successful restore, both files are saved with the new build ID.

## Review focus

1. **Rerun `restore` after a successful restore:** it must be a no-op, not a wipe. Tested in Task 2 (`test_restore_twice_keeps_edits`).
2. **A reply is missing or the wrong command is echoed** (the pad is busy, or the VIA app is open): the tool must error and not write a half-parsed layout. Tested in Task 2 (`test_parse_rejects_misaligned`).
3. **The pad is already in the bootloader:** no backup is possible, so restore uses the last committed backup and says which build it came from. Task 3.
4. **A macro buffer that doesn't fit** in a smaller new buffer: report it and don't truncate silently. Tested in Task 1 (`test_macros_too_big`).
5. **A slot missing from the new layout** (fewer layers): report it as dropped. Tested in Task 1 (`test_dropped_slot`).

---

### Task 1: Merge logic

**Files:**
- Create: `tools/via_merge.py`
- Test: `tools/test_via_merge.py`

**Interfaces (produces):**
- `Slots = dict[str, int]`: slot name to keycode.
- `@dataclass Conflict(slot: str, kept: int, new_default: int)`
- `@dataclass MergeResult(merged: Slots, edits: Slots, conflicts: list[Conflict], dropped: list[str])`
- `edits(old_defaults: Slots, backup: Slots) -> Slots`
- `merge(old_defaults: Slots, backup: Slots, new_defaults: Slots) -> MergeResult`
- `differences(a: Slots, b: Slots) -> list[str]`: sorted names of slots in both whose values differ.
- `merge_macros(backup: bytes, size: int) -> bytes | None`: `None` if the backup is all zero. Raises `ValueError` if non-zero data doesn't fit in `size`. Otherwise returns the backup padded with zeros to `size`.

- [ ] **Step 1: Write the tests** `test_no_edits` (merged == new_defaults), `test_edit_kept`, `test_untouched_takes_new_default`, `test_conflict_edit_wins` (the conflict lists kept and new default), `test_dropped_slot`, `test_macros_empty_is_none`, `test_macros_padded`, `test_macros_too_big`.
- [ ] **Step 2: Run** `python3 -m unittest tools/test_via_merge.py`. Expected: fails on import.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: all pass.

### Task 2: `tools/via-layout.py`

**Files:**
- Create: `tools/via-layout.py`, `tools/test_via_layout.py`

**Interfaces:**
- **Consumes:** Task 1.
- **Produces (CLI):** `backup`, `restore`, `apply SLOT...`, `diff`, `set SLOT KEYCODE` (for testing and quick fixes). Exit 0 on success, 1 on error with a one-line `FAILED:` reason.
- **Slot names:**
  - `L<n> key<k>` for k 1–16 (`[r][c]` with c<4 is `r*4+c+1`).
  - `L<n> knob-left|knob-right|knob-big` for `[0..2][4]`, and `L<n> r3c4`.
  - `L<n> enc<i> cw|ccw`.
  - `macros` for `apply` only.
- **JSON:** `{"build", "shape": {"layers","rows","cols","encoders","macro_size"}, "layers": [{"keys": {name: "0x0268"}, "turns": {"enc0 cw": "0x00A9"}}], "macros": "<hex, trailing zeros trimmed>"}`.
- **`restore` algorithm:**
  1. Load both files.
  2. Send `0x06`, then read the pad, which is now the new defaults.
  3. **Record usable** (the build IDs in the two files match): `merge`, write only the slots where merged ≠ new defaults (`0x05` and `0x15`), then the macros (`0x0F`). Read back and compare to merged. Print the edits and conflicts.
  4. **Otherwise:** restore nothing and print `differences(backup, new_defaults)` with an `apply` hint.
  5. **Save:** `defaults.json` gets the new defaults, with the pad's build ID. On the merge path, also save `layout.json` as the merged layout with the new build ID.
- **Transport:** `run(cmds: list[list[int]]) -> list[list[int]]`, in batches of up to 40 commands per `hidapitester` call. Each reply is 33 bytes; check that the reply count and each echoed command byte match. The parsing lives in `parse_replies(text: str, cmds) -> list[list[int]]` so it can be tested without the pad.

- [ ] **Step 1: Write the tests**:
  - `test_parse_replies` (using the real output captured from the pad).
  - `test_parse_rejects_misaligned`.
  - `test_slot_names_roundtrip` (JSON to slots to JSON).
  - `test_restore_twice_keeps_edits`, using a fake pad object behind the same interface as the HID class.
- [ ] **Step 2: Run** them. Expected: fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the unit tests, then on the pad `tools/via-layout.py backup` and `tools/via-layout.py diff`. Expected: `layout.json` has 8 layers and L1 key1 is `0x0268`; `diff` reports no record yet.
- [ ] **Step 5: Commit** the tool and tests (without `via/`).

### Task 3: Wire into `flash-pad.sh`, docs

**Files:**
- Modify: `tools/flash-pad.sh`, `README.md`, `CLAUDE.md`, `IDEAS.md`, the design doc's "Design" section (the findings above).

- [ ] **Step 1: Add the `--skip-layout` flag.**
- [ ] **Step 2: Back up first.** In the pad-present branch, run `backup` before the dfu-util wait starts. If it fails, exit 2 with a message naming `--skip-layout`.
- [ ] **Step 3: Bootloader branch:** say that the layout can't be read, and that the last backup (with its build) will be used.
- [ ] **Step 4: Restore.** After the `OK:` line, run `restore`. If it fails, exit 3: `the flash worked, but the layout restore failed: run tools/via-layout.py restore`.
- [ ] **Step 5: Docs.**
  - README's VIA section: edits now survive `flash-pad.sh`.
  - CLAUDE.md:
    - flashing notes: the `via/` files get committed after flashing, and the wipe is by day.
    - change loop: step 3 commit, step 4 flash and commit `via/`.
  - IDEAS.md: move this to "Already built".
- [ ] **Step 6: `bash -n tools/flash-pad.sh`,** then commit.

### Task 4: Live test on the pad

- [ ] **Step 1: Rebuild** against the current QMK (`80973aa`), which gives zero warnings and a new `.bin`. Commit it.
- [ ] **Step 2: Bootstrap.** The first flash has no record, so the pad gets the defaults and `defaults.json` is written. Commit `via/`.
- [ ] **Step 3: Make a test edit:** `apply`-style set of `L8 key16` to `0x0173` (`C(KC_F24)`) with `via-layout.py set`. `diff` shows exactly that edit.
- [ ] **Step 4: Rebuild and flash.** Expected output: one edit restored, no conflicts. `diff` still shows `L8 key16`.
- [ ] **Step 5: Remove the test edit** (`set L8 key16` back to its default), then commit `via/`.
- [ ] **Step 6: Hand off to Rahul:** the check is that the pad behaves as before.
