# KB16 macro pad: firmware + AutoHotkey

Rahul's DOIO KB16 macro pad on Windows. Two halves work together:

- **Firmware** (`keyboards/doio/kb16/keymaps/enhanced/`): a custom QMK keymap with VIA support. It owns layers, lighting, the OLED and the layer knob.
- **AutoHotkey v2 script** (`ahk/Macropad.ahk`): turns the pad's F-keys into actions (launch apps, send shortcuts), chosen per layer.

The pad tells the script which layer it's on with an **announce combo**: every time the layer changes, the firmware taps `Ctrl+Alt+Shift+F13` (layer 1) through `Ctrl+Alt+Shift+F20` (layer 8). The script sets its `Layer` variable from that. The two halves share nothing else, so keep that contract intact whenever you change either side.

Feature backlog with trade-offs and decisions already made: **`IDEAS.md`**. Read it when choosing, designing or scoping a new feature.

## Hardware

- **Board:** DOIO KB16 **rev2** (STM32F103, stm32duino bootloader, 128 KB flash, plenty of room). Build rev2 only; Rahul does not have a rev1.
- **Keys:** 4×4 grid plus three knobs with push. 16 RGB LEDs, one under each key, none under the knobs.
- **OLED:** 128×32, which is 21 characters × 4 rows in the default font.
- **Matrix positions:** keys are `[row][col]` with row 0–3 and col 0–3, numbered 1–16 left to right, top to bottom. Knob presses are column 4: `[0][4]` left knob, `[1][4]` right knob, `[2][4]` big knob. `[3][4]` is unused.
- **Encoders (knob turns):** index 2 is the big knob. Indices 0 and 1 are the two small knobs; which one is physically left is unconfirmed. Encoder events reach `process_record_user` with `IS_ENCODEREVENT(record->event)` true, `key.row` = `KEYLOC_ENCODER_CW`/`CCW` and `key.col` = encoder index.

## Repo layout

This folder is a QMK **userspace**: QMK builds straight from it, so nothing is copied into the QMK install.

- `keyboards/doio/kb16/keymaps/enhanced/`: the firmware (`keymap.c`, `config.h`, `rules.mk`). The folder name `enhanced` is the keymap name. It's the `-km` argument and the end of the `.bin` filename.
- `qmk.json`: marks this folder as a userspace and lists the build target.
- `doio_kb16_rev2_enhanced.bin`: the latest build. QMK writes it here, and it's committed alongside the source that produced it.
- `ahk/Macropad.ahk`: the AutoHotkey script.

## Build environment (WSL)

QMK is already installed in WSL (Ubuntu), and this repo is cloned inside the Ubuntu filesystem. Rahul opens it in VS Code over WSL, so Claude Code runs in WSL and calls `qmk` directly. He flashes from Windows with QMK Toolbox.

- **Before the first build in a session,** run `qmk userspace-doctor`. It should report this repo as the userspace with "Userspace enabled: True". If it doesn't, run `qmk config user.overlay_dir="$(realpath .)"` from the repo root.
- **Windows reaches files here through a WSL network path.** QMK Toolbox and AutoHotkey run on Windows and open files from this repo through a path like `\\wsl.localhost\Ubuntu\...`. `wslpath -w <file>` prints the exact Windows path for any file.
- **QMK version:** last built against qmk_firmware commit `8252b63` (2026-11-16). If a newer QMK renames keycodes or APIs, update the keymap to match. If the fix turns out large, ask Rahul before pinning an older QMK.
- **VIA:** it's a VIA keymap (`VIA_ENABLE = yes` in `rules.mk`) and builds from plain qmk_firmware.

## Change loop

Every firmware change goes through these steps, in order. Each step is done when its condition holds.

1. **Edit** files under `keyboards/doio/kb16/keymaps/enhanced/`.
2. **Build** with `qmk compile -kb doio/kb16/rev2 -km enhanced`. It shows full compiler output, while `qmk userspace-compile` prints only a summary. Done when it finishes with zero compiler warnings and a fresh `doio_kb16_rev2_enhanced.bin` is at the repo root.
3. **Commit** the source and the `.bin` together. The message says what changed and what Rahul should check on the pad. AutoHotkey changes get committed too.
4. **Hand off.** Tell Rahul the `.bin` is ready, and give its Windows path from `wslpath -w doio_kb16_rev2_enhanced.bin` so he can open it in QMK Toolbox. Remind him that flashing wipes his VIA layout, and give him the checklist from the commit message.
5. **Tag a known-good build:** once Rahul confirms the firmware works on the pad, tag that commit `fw-vN`. The last delivered build was v4, so the next is `fw-v5`. To roll back, run `git checkout fw-vN -- doio_kb16_rev2_enhanced.bin` and flash that file.

## Flashing

- **Flash** with QMK Toolbox. To enter bootloader mode, hold the top-left key while plugging the pad in (bootmagic), or assign keycode `0x7C00` (`QK_BOOT`) to a key in VIA and press it.
- **Every new build wipes VIA's saved layout**, because QMK resets VIA's storage when the build date changes. `keymap.c` is the source of truth for defaults: anything Rahul should keep across flashes belongs in `keymap.c`, not just in VIA. VIA macros are wiped too, so use plain key combos (`C(A(KC_EQL))`) instead of VIA macros.
- **Testing:** Claude can't test on the pad. A firmware change is done at step 4 of the change loop. For AutoHotkey, ask Rahul to run it, or use `AutoHotkey64.exe /Validate` for a syntax check if it's available.

## Current firmware behavior

All of this is in `keymap.c`. The section headings in the file match the bullets.

- **Layers:** 8 (`DYNAMIC_KEYMAP_LAYER_COUNT` in `config.h`).
  - **Layer 1:** keys 1–16 are `Shift+F13`, Prev, Play, Next / F13, F14, F15, Calc / F17, F18, F19, Delete / Home, PgUp, PgDn, End. Key 1 (`Shift+F13`) is the script's info key.
  - **Layers 2–8:** `FKEY_LAYER`, which is `Shift+F13`–`Shift+F16` on the top row, then F13–F24. Knob presses are transparent, so they fall through to layer 1.
  - **Why no F9–F12:** the pad only sends F13–F24 and Shift+F13–F16 because F9–F12 exist on Rahul's real keyboard. A hooked F11 would break fullscreen everywhere.
- **Knob presses:** the left knob is the **layer knob** (`LYR_NEXT` = `QK_USER_0` = `0x7E40`, shown as that number in VIA). The right knob press is unassigned (`KC_NO`). The big knob press is Mute on every layer; that's Rahul's explicit choice.
- **Layer knob:**
  - tap: next layer (wraps)
  - hold and press key 1–8: jump to that layer
  - hold and turn **any** knob: right is next, left is previous
  - hold alone for at least `LAYER_HOLD_MS` (400 ms): back to layer 1, which also re-syncs the script
  - Any key or knob action during the hold cancels the return to layer 1. A key press eaten by a layer jump also has its release eaten (the `swallowed` bitmask).
- **Knob turns (`encoder_map`):** shown left turn / right turn.
  - **Layer 1:** rewind/fast-forward, Down/Up, Volume -/+
  - **Layer 2:** `>`/`<`, scroll, `Ctrl+Alt+-`/`=` (per-app volume, which the script catches)
  - **Layer 3:** J/L, scroll, Undo/Redo
  - **Layer 4:** `[`/`]`, scroll, Zoom -/+
  - **Layers 5–8:** transparent, so they behave like layer 1
- **Announce combo:** `layer_state_set_user` only sets a flag. `housekeeping_task_user` sends the combo, because sending keys from inside a layer change can fire in the middle of a key press. It also announces once, 1 s after boot.
- **Per-layer lighting (`layer_lights[]`):** a color plus an effect per layer. Brightness is left alone so VIA's slider still works, but VIA's color and effect are overwritten on each layer change.
  - **Layers 1–4:** 1 warm white solid, 2 coral breathing, 3 amber band sweep (`BAND_VAL`), 4 green white-band sweep (`BAND_SAT`)
  - **Layers 5–8:** 5 teal breathing, 6 blue solid, 7 violet spinning pinwheel (`BAND_PINWHEEL_VAL`), 8 pink `SOLID_REACTIVE`
  - **Choosing effects:** only use effects that keep one color, so the color always identifies the layer. The rainbow, cycle, beacon, raindrop and pixel effects ignore the hue. `HUE_WAVE` and `HUE_PENDULUM` shift the hue too little to see on 16 LEDs, and Rahul rejected them. Effects that stay dark until a key is pressed hide which layer you're on.
  - **Confusable colors:** coral/amber and blue/violet are the pairs most easily confused, so give each pair contrasting effects.
- **OLED:** shows `LAYER N` centered on row 1. When a knob is turned or pressed, it shows that action's label for `KNOB_LABEL_MS` (1 s), then goes back. Turning repeatedly keeps the label up.
  - **Where the labels come from:** QMK hands `process_record_user` the key code **currently assigned** to the knob, so VIA remaps are reflected without a reflash. `label_for()` turns that key code into text. Known keys and combos get friendly names (`named_combo()`), other combos are spelled out (`C+S+F5`), and VIA macros show `MACRO n`.
  - **Redrawing:** the screen only redraws when `oled_dirty` is set. It calls `oled_clear()` first, because the board's 5 s boot logo is a raw bitmap that would otherwise stay underneath the text. Rahul removed a small layer tag in the corner; keep labels on their own.
  - **Sleep:** the screen turns off after 60 s with no input (QMK's default) and wakes on any key or knob action.

## Current AutoHotkey script

`ahk/Macropad.ahk` is the version delivered on 2026-11-16. **Rahul may have edited his copy since.** Get his current file before you change anything, and build on that.

- **`PadKeys`:** the hotkey each pad button sends (button 1 = top left), the same on every F-key layer.
- **`Actions[layer][button] := [label, fn]`:**
  - `fn = 0` means label only: the firmware handles that key (media, Calc, nav), and the label just appears in the info window.
  - `Actions[0]` is the fallback for every layer. Button 1 is `Info`, which shows a 4×4 grid of the current layer's labels.
  - To add an action, add one entry to the right `Actions[n]` map. Nothing else needs wiring.
- **`SetLayer`:** registered for the eight announce combos. It sets `Layer` and shows a fading toast at the top left.
- **`Toast` class:** one reusable fading window, built once and re-shown, so presses don't stack windows. It uses `NoActivate` so it never steals focus.
- **`AdjustVolume`:** changes the volume of the focused app through SoundVolumeView at `D:\Programs\SoundVolumeView\SoundVolumeView.exe`. It's bound to `Ctrl+Alt+=`/`-`, which the big knob sends on layer 2.
- **Layer 1 actions:**
  - SoundSwitch audio-device toggle (sends `Ctrl+Alt+F11`)
  - Windows Terminal, and Windows Terminal with the `"Server SSH"` profile
  - Cut, Copy, Paste

## Constraints to respect

- **The script can't tell where a key came from.** Knob turns send ordinary keys, so the script can't tell a knob's `Ctrl+Z` from the keyboard's. Hook only keys the pad alone sends: F13–F24, Shift+F13–F16 and the announce combos. Anything that has to know a press came from the pad needs raw HID (see `IDEAS.md`).
- **Only one copy of the script should run.** If an old copy is running alongside, every key fires twice.
- **Every firmware change ends in a reflash, which wipes VIA's layout.** Say so whenever you hand over a new `.bin`.

## Rahul's preferences

- Challenge his ideas and point out flaws before agreeing. Say why.
- He decides the features; you make the engineering calls within them, and name any call he might disagree with.
