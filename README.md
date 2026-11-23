# Macropad

My DOIO KB16 macro pad setup for Windows: custom QMK firmware for the pad, plus an AutoHotkey v2 script that turns its keys into actions like opening programs or sending shortcuts. It's mainly for my own use, but it's public in case it helps anyone with the same pad, or anyone who wants to build on it.

## How it fits together

- **Firmware** (`keyboards/doio/kb16/keymaps/enhanced/`): a QMK keymap with VIA support for the KB16 rev2. It handles layers, lighting, the OLED and the knobs.
- **Script** (`ahk/Macropad.ahk`): listens for the F13–F24 keys the pad sends and runs whatever action belongs to that key on the current layer.

The pad tells the script which layer it's on. Every time the layer changes, the firmware taps a hidden combo, from `Ctrl+Alt+Shift+F13` for layer 1 to `Ctrl+Alt+Shift+F20` for layer 8, and the script switches to match. One press changes both, and they can't drift apart.

## The pad

Keys are numbered 1–16, left to right and top to bottom. There are three knobs, two small and one big, and each one turns and presses.

### Layers

There are 8 layers. Layer 1 is the base layer. Entries marked * need the script running.

| | | | |
|---|---|---|---|
| Info* | Previous track | Play/Pause | Next track |
| Switch audio device* | Windows Terminal* | Terminal: Server SSH* | Calculator |
| Cut* | Copy* | Paste* | Delete |
| Home | Page Up | Page Down | End |

On layers 2–8, every key sends an F-key (`Shift+F13`–`Shift+F16` on the top row, F13–F24 on the rest), so the script decides what each key does. Key 1 is Info on every layer. These layers are free for new actions; so far only layer 2 has one, a test action on key 5.

The pad never sends F9–F12, because those exist on a normal keyboard: taking over F11 would break fullscreen everywhere.

### Knob presses

- **Left knob:** the layer knob (below).
- **Right knob:** unassigned.
- **Big knob:** Mute, on every layer.

### The layer knob

- **Tap:** next layer, wrapping from 8 back to 1.
- **Hold and press key 1–8:** jump straight to that layer.
- **Hold and turn any knob:** right goes to the next layer, left to the previous one.
- **Hold for 0.4 s or more on its own, then let go:** back to layer 1. This also re-syncs the script if it ever gets out of step.

### Knob turns

Shown as left turn / right turn. Which small knob is encoder 0 and which is encoder 1 hasn't been confirmed yet.

| Layer | Small knob (encoder 0) | Small knob (encoder 1) | Big knob |
|---|---|---|---|
| 1 | Rewind / Fast-forward | Down / Up | Volume − / + |
| 2 | `>` / `<` | Scroll down / up | Focused app's volume − / +* |
| 3 | J / L | Scroll down / up | Undo / Redo |
| 4 | `[` / `]` | Scroll down / up | Zoom out / in |
| 5–8 | same as layer 1 | same as layer 1 | same as layer 1 |

### Lighting

Each layer has its own color and effect, so you can tell the layer at a glance.

| Layer | Color | Effect |
|---|---|---|
| 1 | Warm white | Solid |
| 2 | Coral | Slow breathing |
| 3 | Amber | Band sweep |
| 4 | Green | White band sweep |
| 5 | Teal | Slow breathing |
| 6 | Blue | Solid |
| 7 | Violet | Spinning pinwheel |
| 8 | Pink | Solid, keys flash when pressed |

VIA's brightness slider still works. VIA's color and effect settings are overwritten on every layer change.

### OLED

The screen shows `LAYER N`. Turning or pressing a knob shows what it did (`VOL +`, `UNDO`, `C+S+F5` and so on) for a second, then goes back. The labels follow whatever the knob is currently assigned to, so remapping a knob in VIA updates its label without reflashing. The screen turns off after 60 s without input and wakes on any key or knob.

### VIA

The firmware works with [VIA](https://usevia.app/) for remapping. The layer knob shows up in VIA as `0x7E40`.

Every reflash wipes VIA's saved layout and macros. The defaults live in `keymap.c`, so anything worth keeping across flashes belongs there.

## The script

`ahk/Macropad.ahk` needs AutoHotkey v2. What it does:

- **Layer toast:** shows the layer number at the top left when the layer changes, then fades. It never takes focus.
- **Info (key 1, every layer):** shows a 4×4 grid of what each key does on the current layer.
- **Layer 1 actions:** switch audio device (key 5), Windows Terminal (key 6), Windows Terminal with the "Server SSH" profile (key 7), and Cut, Copy, Paste (keys 9–11).
- **Per-app volume:** `Ctrl+Alt+=` and `Ctrl+Alt+-` turn the focused app's volume up or down by 5. The big knob sends these on layer 2, and they work from the keyboard too.

Run only one copy. If an older copy from another folder is still running, every key fires twice.

### Adding an action

Add one entry to the `Actions` map for that layer. Nothing else needs wiring:

```ahk
Actions[3] := Map(5, ["Spotify", () => Run("spotify.exe")])
```

The label is what the Info grid shows. Use `0` instead of a function for a key the firmware already handles, so it gets a label but no action.

### Required programs

- [SoundSwitch](https://soundswitch.aaflalo.me/) for switching audio devices, with its switch hotkey set to `Ctrl+Alt+F11`.
- [SoundVolumeView](https://www.nirsoft.net/utils/sound_volume_view.html) for per-app volume. The script expects it at `D:\Programs\SoundVolumeView\SoundVolumeView.exe`; change `programPath` in `AdjustVolume` if yours is elsewhere.
- Windows Terminal, with a profile named "Server SSH" for key 7.

## Building and flashing

This folder is a QMK userspace, so QMK builds straight from it. With QMK installed:

```bash
qmk config user.overlay_dir="$(realpath .)"   # once
qmk compile -kb doio/kb16/rev2 -km enhanced
```

That writes `doio_kb16_rev2_enhanced.bin` to the repo root.

To flash, run `tools/flash-pad.sh` from WSL. It reboots the pad into its bootloader, flashes it and checks that the new build is running. It needs a one-time setup, described in [docs/flashing-setup.md](docs/flashing-setup.md). To flash by hand instead, hold the top-left key while plugging the pad in, then flash the `.bin` with QMK Toolbox.
