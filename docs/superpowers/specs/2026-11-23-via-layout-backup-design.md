# Keep VIA edits across flashes: design

Status: approved by Rahul, 2026-11-23.

## Why

Every new build wipes VIA's saved layout. The keymap, knob turns and macros reset to the `keymap.c` defaults, because QMK resets VIA's storage when the build date changes. Rahul has no VIA edits today. If he makes some, his custom setup is what works for him, so it should survive flashing. A firmware update is for getting new features, not for resetting his layout.

## Goals

- VIA edits to keys, knob turns and macros survive `tools/flash-pad.sh`.
- Keys he never edited take the new build's defaults, so new features arrive.
- When a new build changes a key he edited, his edit wins and he's told which new default he didn't get.
- No firmware change.

## Non-goals

- Lighting: brightness lives in QMK's own config, not VIA's storage, and already survives. Color and effect are set per layer by the firmware.
- VIA layout options: the KB16 has none.
- Flashing done with QMK Toolbox: only `flash-pad.sh` backs up and restores. A manual restore command covers recovery.

## Anti-goals

- Losing edits silently. That includes a flash that goes ahead without a backup.
- A new default silently not showing up because an old edit covers it.

## Approaches

- **A. Restore only his edits (chosen).** Save each build's defaults right after it's flashed. On the next flash, edits = the pad's layout minus those saved defaults. Apply them on top of the new build. Rahul picked this because it's the only one that keeps both his edits and new features.
- **B. Restore the whole old layout.** Simpler, but it puts old defaults back on untouched keys and undoes new features.
- **C. Back up always, restore on request.** Safest, but easy to forget, so edits stay lost.

## Design

**New tool `tools/via-layout.py`** (Python 3, standard library only). It talks VIA's raw HID protocol through `hidapitester.exe`, putting a whole read or write into one `hidapitester` call (it runs its commands in order). It reads and writes:

- **Sizes come from the pad, not constants:** the layer count from `0x11`, the macro buffer size from `0x0D`. Rows, columns and encoder count can't be queried through VIA, so they're parameters, set once for the KB16 (4 × 5, 3 encoders).
- **Keymap:** layers × rows × cols, 2 bytes each (big-endian), 320 bytes on the KB16. It uses `0x12` get buffer and `0x13` set buffer, in chunks of up to 28 bytes.
- **Knob turns:** layers × encoders × 2 directions. It uses `0x14` get encoder and `0x15` set encoder.
- **Macros:** the whole buffer. It uses `0x0D` for the buffer size, `0x0E` get and `0x0F` set.

**Code split:** the merge is pure functions (layouts in, merged layout and a list of conflicts out) with no HID or file I/O, in `tools/via_merge.py`. `tools/via-layout.py` does the HID, files and CLI around it. The merge is the part a future app reuses.

**Files, committed under `via/`:**

- `via/defaults.json`: the defaults of the build now on the pad, with its build ID.
- `via/layout.json`: the pad's layout read just before the last flash (Rahul's setup).
- Keycodes are stored as hex, by layer, key number (1–16, knob presses as `knob-left`, `knob-right`, `knob-big`) and encoder direction, so a git diff is readable.

**Flow inside `flash-pad.sh`:**

1. **Before rebooting the pad:** read the full layout into `via/layout.json`. If the read fails, stop without flashing. `--skip-layout` overrides this.
2. **Flash** as today.
3. **After `OK: pad is running build ...`:**
   - **Same build ID as before:** VIA's storage wasn't wiped, so do nothing.
   - **Otherwise:** read the pad, which is now exactly the new defaults, and keep that in memory.
   - **Merge** (step 4), write the result to the pad, and read it back to verify.
   - Save the new defaults to `via/defaults.json`.
4. **Merge rules,** per slot (one key, one knob direction):
   - An **edit** is a slot where `layout` differs from `defaults.json`.
   - Edits are written over the new defaults.
   - A **conflict** is an edit where the new default also differs from the old default. The edit wins, and the script prints, for example, `layer 3 key 6: kept your C(KC_T); new default KC_F18 not applied`.
   - **Macros:** the defaults are empty, so any non-empty macro buffer is restored as a whole.
5. **No usable record:** `defaults.json` is missing, or its build ID isn't the build that was on the pad. This covers the first run and a flash done with QMK Toolbox. The script can't tell edits from old defaults, so it restores nothing. It prints every slot where the backup differs from the new defaults, then saves the new defaults. `tools/via-layout.py apply <slot>...` puts back the slots Rahul picks.

**Manual commands:**

- `via-layout.py backup` reads the pad into `via/layout.json`.
- `via-layout.py restore` reruns the merge against what's on the pad.
- `via-layout.py apply <slot>...` copies chosen slots from the backup.
- `via-layout.py diff` shows Rahul's edits against the defaults.

**Failures after the flash:** the backup file is already saved, so the script prints the error and tells Rahul to run `tools/via-layout.py restore`.

## Calls made (Claude's, open to correction)

- **The `via/` files are committed** with the flash, so VIA edits show up in git history instead of living only on the pad. The script doesn't commit; Claude commits them in the change loop's commit step after flashing.
- **The backup is required:** if it fails, nothing is flashed. A flash without a backup is exactly the silent loss this exists to prevent.
- **Python over bash** for the protocol and merge logic: JSON plus per-slot logic gets fragile in bash. `flash-pad.sh` already uses `python3`.

## Testing

- **Unit tests** for the merge (`tools/test_via_layout.py`, plain `unittest`): no edits, an edit, a conflict, macros, no record, same-build reflash.
- **On the pad:**
  - `backup` and `diff` against the current pad.
  - Then the tool sets a test edit, for example layer 8 key 16 to `KC_F24` with `Ctrl`.
  - Flash a rebuild (QMK has moved to `80973aa`, so a rebuild is a real commit anyway) and confirm the edit survived and untouched keys match the new defaults.
  - Remove the test edit.

## Public version (future editor app)

The merge rules carry over unchanged. QMK hard-codes the wipe (VIA's storage is checked against the build date), so any public tool that flashes needs this feature. Four things don't carry over:

- **Storage:** users have no git repo. The app keeps each user's layout and the last-flashed defaults per device, in its own app data.
- **Transport:** the app talks HID directly, not through `hidapitester`, WSL and bash.
- **Sizes:** rows, columns and encoder count come from the keyboard's definition (as VIA's JSON provides), not from KB16 parameters.
- **Same-build check:** it depends on this firmware's `F0 01` build ID. Stock QMK firmware has no equivalent (`VIA_FIRMWARE_VERSION` is 0 unless set), so the app needs another way to tell whether the layout was wiped.

## Left to the builder

- The exact JSON shape, the CLI output wording, and how errors are reported by `hidapitester`.
- Whether the first-run listing names keycodes (`KC_MUTE`) or shows hex. Names are nicer, so reuse what `label_for()` knows if it's cheap, otherwise hex.
