# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# KB16 macro pad: firmware + AutoHotkey

Rahul's DOIO KB16 macro pad on Windows. Two halves work together:

- **Firmware** (`keyboards/doio/kb16/keymaps/enhanced/`): a custom QMK keymap with VIA support. It owns layers, lighting, the OLED and the layer knob.
- **AutoHotkey v2 script** (`ahk/Macropad.ahk`): turns the pad's F-keys into actions (launch apps, send shortcuts), chosen per layer.

The pad tells the script which layer it's on with an **announce combo**: every time the layer changes, the firmware taps `Ctrl+Alt+Shift+F13` (layer 1) through `Ctrl+Alt+Shift+F20` (layer 8). The script sets its `Layer` variable from that. The two halves share nothing else, so keep that contract intact whenever you change either side.

- **What the pad and script do** (each layer's keys, knob turns, lighting, script actions): `README.md`. It's the summary for people; the code is the source of truth.
- **Feature backlog** with trade-offs and decisions already made: `IDEAS.md`. Read it when choosing, designing or scoping a new feature.

## Hardware

- **Board:** DOIO KB16 **rev2** (STM32F103, stm32duino bootloader, 128 KB flash, plenty of room). Build rev2 only; Rahul does not have a rev1.
- **Keys:** 4×4 grid plus three knobs with push. 16 RGB LEDs, one under each key, none under the knobs.
- **OLED:** 128×32, which is 21 characters × 4 rows in the default font.
- **Matrix positions:** keys are `[row][col]` with row 0–3 and col 0–3, numbered 1–16 left to right, top to bottom. Knob presses are column 4: `[0][4]` left knob, `[1][4]` right knob, `[2][4]` big knob. `[3][4]` is unused.
- **Encoders (knob turns):** index 2 is the big knob. Indices 0 and 1 are the two small knobs; which one is physically left is unconfirmed. Encoder events reach `process_record_user` with `IS_ENCODEREVENT(record->event)` true, `key.row` = `KEYLOC_ENCODER_CW`/`CCW` and `key.col` = encoder index.

## Repo layout

This folder is a QMK **userspace**: QMK builds straight from it, so nothing is copied into the QMK install.

- `keyboards/doio/kb16/keymaps/enhanced/`: the firmware (`keymap.c`, `config.h`, `rules.mk`, and the LED driver `ws2812_custom.c`). The folder name `enhanced` is the keymap name. It's the `-km` argument and the end of the `.bin` filename.
- `qmk.json`: marks this folder as a userspace and lists the build target.
- `doio_kb16_rev2_enhanced.bin`: the latest build. QMK writes it here, and it's committed alongside the source that produced it.
- `ahk/Macropad.ahk`: the AutoHotkey script.

## Build environment (WSL)

QMK is already installed in WSL (Ubuntu), and this repo is cloned inside the Ubuntu filesystem. Rahul opens it in VS Code over WSL, so Claude Code runs in WSL and calls `qmk` directly. He flashes from Windows with QMK Toolbox.

- **Before the first build in a session,** run `qmk userspace-doctor`. It should report this repo as the userspace with "Userspace enabled: True". If it doesn't, run `qmk config user.overlay_dir="$(realpath .)"` from the repo root.
- **Windows reaches files here through a WSL network path.** QMK Toolbox and AutoHotkey run on Windows and open files from this repo through a path like `\\wsl.localhost\Ubuntu\...`. `wslpath -w <file>` prints the exact Windows path for any file.
- **QMK version:** nothing pins it; builds use whatever `~/qmk_firmware` was last updated to. Put its commit (`git -C ~/qmk_firmware log -1 --format='%h %cs'`) in every firmware commit message, so a later breakage can be traced to a QMK update. Builds up to `e70b794` used `8252b63` (2026-11-16). If a newer QMK renames keycodes or APIs, update the keymap to match. If the fix turns out large, ask Rahul before pinning an older QMK.
- **VIA:** it's a VIA keymap (`VIA_ENABLE = yes` in `rules.mk`) and builds from plain qmk_firmware.

## Change loop

Every firmware change goes through these steps, in order. Each step is done when its condition holds.

1. **Edit** files under `keyboards/doio/kb16/keymaps/enhanced/`.
2. **Build** with `qmk compile -kb doio/kb16/rev2 -km enhanced`. It shows full compiler output, while `qmk userspace-compile` prints only a summary. Done when it finishes with zero compiler warnings and a fresh `doio_kb16_rev2_enhanced.bin` is at the repo root.
3. **Commit** the source and the `.bin` together. The message says what changed, what Rahul should check on the pad, and the QMK commit it was built against. If the change alters anything `README.md` describes, update it in the same commit. AutoHotkey changes get committed too, with the same README rule.
4. **Flash** with `tools/flash-pad.sh`. It refuses uncommitted changes, so whatever is on the pad always matches a commit. Done when it exits 0 and prints `OK: pad is running build ...`, which means the pad reported the same build ID that's inside the `.bin`, and the VIA layout restore reported no error. Then commit `via/` (the layout backup and the new build's defaults). Relay any `CONFLICT` or `DROPPED` lines to Rahul. If it fails, relay its recovery steps to Rahul; they need his hands on the pad.
5. **Hand off for testing.** Tell Rahul the new build is on the pad, and give him the checklist from the commit message.
6. **Tag a known-good build:** once Rahul confirms the firmware works on the pad, tag that commit `fw-vN`. The last build before automatic flashing was v4, so the first flashed this way is `fw-v5`. To roll back, run `git checkout fw-vN -- doio_kb16_rev2_enhanced.bin`, commit that, and flash.

## Flashing

- **`tools/flash-pad.sh`** reboots the pad into its bootloader over raw HID, flashes it with `dfu-util`, then confirms the build ID. It drives Windows programs (`hidapitester.exe`, `dfu-util.exe` in `C:\Tools\kb16-flash\`) through WSL interop. If those tools are missing, point Rahul to `docs/flashing-setup.md`.
- **The UAC prompt:** after the download, the stm32duino bootloader waits for a USB reset that `dfu-util -R` can't send on Windows. The script then restarts the device with `pnputil /restart-device`, which needs admin, so a UAC prompt appears on Rahul's screen. Tell him to expect it before you flash. If it's declined, he replugs the pad with no key held.
- **`tools/flash-pad.sh --check`** reports what's connected and which build the pad is running, without flashing. Use it to find out what's on the pad.
- **Manual fallback:** hold the top-left key while plugging the pad in (bootmagic), then rerun the script, which notices a pad already in the bootloader. QMK Toolbox also still works. This is the only route for a build that crashes before it can answer raw HID.
- **VIA layout across flashes:**
  - **What QMK does:** QMK resets VIA's storage when the build **day** changes. The check ignores the time, so a same-day rebuild would keep the old layout and never load new `keymap.c` defaults.
  - **What `flash-pad.sh` does about it:** `tools/via-layout.py` backs the layout up first. Afterwards it always resets the keymap to the build's defaults (VIA command `0x06`), then reapplies Rahul's edits: the slots where the backup differs from `via/defaults.json`, the old build's defaults.
  - **Edits win over new defaults.** `CONFLICT` lines report that.
  - **No usable record** (the first flash, or after QMK Toolbox): nothing is restored, and the differences are listed.
  - **Keep the merge rules in `tools/via_merge.py`,** pure and tested (`python3 -m unittest` in `tools/`). A future editor app reuses them; see the design in `docs/superpowers/specs/`.
  - **Defaults still belong in `keymap.c`.** It's what other builds and the README describe. Still use plain key combos (`C(A(KC_EQL))`) over VIA macros.
- **Testing:** the script proves the right build is running. Whether it behaves right still needs Rahul's hands and eyes, so a firmware change is done at step 5 of the change loop. For AutoHotkey, ask Rahul to run it, or use `AutoHotkey64.exe /Validate` for a syntax check if it's available.

## Firmware decisions and gotchas

What each layer does is in `keymap.c` and summarized in `README.md`. This section holds what neither says: the reasons and the traps.

- **Keys and knobs:**
  - **No F9–F12:** the pad only sends F13–F24 and Shift+F13–F16 because F9–F12 exist on Rahul's real keyboard. A hooked F11 would break fullscreen everywhere.
  - **Key 1 is `Shift+F13` on every layer:** it's the script's Info key (`Actions[0]`), so keep it there.
  - **Big knob press is Mute on every layer:** Rahul chose that explicitly.
  - **The layer knob** is `LYR_NEXT` = `QK_USER_0` = `0x7E40`, which VIA shows only as that number. A key press eaten by a layer jump also has its release eaten (the `swallowed` bitmask), or the F-key's release would leak to the PC.
- **Announce combo:** `layer_state_set_user` only sets a flag. `housekeeping_task_user` sends the combo, because sending keys from inside a layer change can fire in the middle of a key press. It also announces once, 1 s after boot.
- **Lighting (`layer_lights[]`):**
  - **LED driver:** `ws2812_custom.c` (`WS2812_DRIVER = custom`) sends the LED data with exact, branch-free pulse widths. QMK's stock bitbang driver held a "0" bit high for ~400–500 ns on this board, which the LEDs misread as a "1", so dim colors and fades showed random colors. The hardware PWM driver can't be used: TIM1 (the only timer on pin A10) has its DMA request on DMA1 channel 5, which the OLED's I2C2 driver allocates. After editing the driver, check the pulse widths in the disassembly (`~/.local/share/qmk/bin/arm-none-eabi-objdump -d` on the `.elf`, function `send_byte`): the pin writes must be separated only by NOPs.
  - **Brightness is left alone** so VIA's slider still works; color and effect are overwritten on each layer change.
  - **Choosing effects:** only use effects that keep one color, so the color always identifies the layer. The rainbow, cycle, beacon, raindrop and pixel effects ignore the hue. `HUE_WAVE` and `HUE_PENDULUM` shift the hue too little to see on 16 LEDs, and Rahul rejected them. Effects that stay dark until a key is pressed hide which layer you're on.
  - **Confusable colors:** coral/amber and blue/violet are the pairs most easily confused, so give each pair contrasting effects.
- **OLED:**
  - **Where the labels come from:** QMK hands `process_record_user` the key code **currently assigned** to the knob, so VIA remaps are reflected without a reflash. `label_for()` turns that key code into text: known keys and combos get friendly names (`named_combo()`), other combos are spelled out (`C+S+F5`), and VIA macros show `MACRO n`.
  - **Redrawing:** the screen only redraws when `oled_dirty` is set. It calls `oled_clear()` first, because the board's 5 s boot logo is a raw bitmap that would otherwise stay underneath the text.
  - **No corner layer tag:** Rahul removed one; keep labels on their own.
- **Flash tools (raw HID, command byte `0xF0`):**
  - **What it is:** the firmware's custom command channel, sitting on VIA's raw HID channel (usage page `0xFF60`, usage `0x61`).
  - **Subcommands:**
    - `F0 01` returns the build ID: `QMK_BUILDDATE`, unique to the second, also stored in the `.bin` behind a `KB16ID:` marker.
    - `F0 02 'B' 'O' 'O' 'T'` reboots into the bootloader. The reboot happens 100 ms later, so the reply gets out first.
  - **Adding a raw HID feature:** add a subcommand under `0xF0` in `via_command_kb` instead of taking another command byte, and keep the two existing subcommands working. `hid_cmd` in `tools/flash-pad.sh` shows how to talk to the pad from WSL.

## AutoHotkey script

- **Rahul may have edited his copy.** Get his current file before you change anything, and build on that.
- **Adding an action** is one entry in the right `Actions[n]` map; nothing else needs wiring. `fn = 0` means label only: the firmware handles that key (media, Calc, nav), and the label just appears in the Info grid.

## Constraints to respect

- **The script can't tell where a key came from.** Knob turns send ordinary keys, so the script can't tell a knob's `Ctrl+Z` from the keyboard's. Hook only keys the pad alone sends: F13–F24, Shift+F13–F16 and the announce combos. Anything that has to know a press came from the pad needs raw HID (see `IDEAS.md`).
  - **Known exception:** `AdjustVolume` hooks `Ctrl+Alt+=`/`-`, which the big knob sends on layer 2 but the real keyboard can send too. Rahul accepted this. Leave it as is, and don't add more hooks like it.
- **Only one copy of the script should run.** If an old copy is running alongside, every key fires twice.
- **Every firmware change ends in a reflash, which wipes VIA's layout.** Say so whenever you hand over a new `.bin`.
