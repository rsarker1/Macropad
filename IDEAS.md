# Feature backlog

Ideas from planning with Rahul, grouped by what they need. Each one notes the catch that came up in discussion. Status is as of 2026-11-22. Rahul chooses what gets built, so treat these as options, not a queue.

## Already built

- **Color and effect per layer.**
- **Layer knob hold-and-turn.**
- **Jump straight to a layer:** hold the layer knob and press key 1–8.
- **Knob labels on the OLED.**

For how each one works, see `README.md`.

## AutoHotkey only

- **Per-app actions with `#HotIf WinActive(...)`.**
  - **What:** the same pad key does different things depending on the focused app.
  - **Why it's cheap:** layers 2–8 all send identical F-keys, so the firmware layer is effectively a page number that the script reads. App awareness can live entirely in the script, with no firmware change.
  - **Status:** recommended as the first step toward app-aware behavior.
- **Move the active window to another monitor.**
  - **Why:** Rahul plans a desk with a 55" TV above a 27" monitor and a small 15.6" monitor on the left.
- **Actions in a config file** (INI or JSON) that reloads automatically when it changes.
  - **Why:** remapping keys wouldn't require editing code.

## Firmware only (not built)

- **Tap vs hold on specific keys.**
  - **Catch:** every tap waits about 200 ms to see if it becomes a hold. Use it only on keys like app launchers, never on media, navigation or Delete.
- **Knob acceleration.**
  - **What:** spinning faster takes bigger steps.
  - **Catch:** apply it only to volume and scrolling. Undo/Redo and zoom must stay one step at a time.

## Needs raw HID (deferred)

Raw HID is a two-way data channel over USB that VIA already uses. The firmware already has a custom command channel on it (`0xF0`, used by the flash tools; see `CLAUDE.md`), and new features become subcommands there. Request-and-reply from WSL through `hidapitester.exe` is built (`hid_cmd` in `tools/flash-pad.sh`); its first real-hardware run is Rahul's first automatic flash. What doesn't exist yet is the pad sending messages on its own, unprompted.

- **Pad → PC:**
  - **What:** the pad could report knob events like "knob 3 turned right, sent Ctrl+Z" while still sending the real key, so the knobs keep working without the script.
  - **Status:** Rahul chose OLED labels instead, for now.
  - **Unverified:** whether AutoHotkey can receive these messages through Windows Raw Input (`WM_INPUT`, usage page `0xFF60`, usage `0x61`). Test that before building on it.
- **PC → pad:**
  - **What:** the script could tell the pad to change layer, or send text for the OLED.
  - **Catch:** sending these from AutoHotkey likely needs `hidapi.dll` through `DllCall`, or calling `hidapitester.exe` as the flash tools do.
- **What raw HID would unlock:**
  - **A 4×4 grid of key labels on the OLED.** Each label can be 5 characters, since 21 ÷ 4 leaves room for 5. The script would send them from its `Actions` table.
  - **Replace the announce combos with real messages,** so no hidden keystrokes can leak into apps.
  - **Status lights from the PC,** for example a key that turns red when the mic is muted.
  - **Switch layers automatically by app.** It only works well with all four of these rules:
    1. Switch only when the focused app changes, not on every focus event.
    2. Debounce, so quick Alt-Tabs and pop-ups don't flip the layer.
    3. Switch only for apps on a list.
    4. A manual layer choice holds until the app changes.

    Without the OLED label grid, Rahul loses track of what the keys do, so build the grid first.

## Long-term: companion app and agent approval pad

Rahul is considering a bigger project to replace AutoHotkey with a companion app (Python or Go) that talks to the pad over raw HID. The first slice is an **approval panel for AI coding agents**:

- **What it does:**
  - A Claude Code hook runs before each tool call and asks the pad.
  - The pad lights up and the OLED shows the request.
  - A key approves or denies it, and a knob scrolls through pending requests.
- **Design rules:**
  - **Fail closed:** deny if the pad is unplugged or anything errors.
  - **Timeouts:** if nobody responds, fall back to the normal on-screen prompt.
  - **Audit log:** record every approval and denial.
- **Engineering practices** (it doubles as a portfolio project):
  - a versioned protocol spec
  - a software simulator of the pad for tests
  - CI that builds the firmware and runs tests
  - a design doc and threat model
  - structured logs
- **Build order:** start with a thin slice (raw HID, OLED request display, one hook script) and grow it into the full app. Don't build all the plumbing first.

### Lessons for a public QMK editor app (from `tools/flash-pad.sh`, 2026-11-23)

Rahul also plans a public visual QMK editor ("like Vial but better"). What building automatic flashing for this pad taught:

- **Flashing is one code path per bootloader.** This pad's stm32duino bootloader waits for a USB reset after a download; STM32's built-in DFU bootloader can be told to start the firmware itself; RP2040 reboots on its own after a UF2 copy. Vial leaves flashing to QMK Toolbox, so in-app flashing is a differentiator but also the costliest feature. Consider leaving it out of the first version.
- **Windows can't send the stm32duino reset without admin.** `dfu-util -R` doesn't do a real USB reset under WinUSB. Restarting the device (`pnputil /restart-device`) works, but needs admin.
  - **App pattern:** try the normal way; if the board is still in the bootloader, ask for elevation once, only then; if declined, ask the user to unplug and replug (no key held).
  - **Rejected:** a scheduled task that runs as admin with no prompt. It's convenient on Rahul's PC, but a standing elevated task is a security liability to ship to users.
  - **Unverified:** on Linux and macOS, libusb can probably send a real reset without admin.
- **The firmware side carries over as is:** the build-ID query (`F0 01`), reboot-to-bootloader (`F0 02 'BOOT'`), and checking the build ID after flashing to prove the flash took.
- **VIA's layout survives a reflash only when the build date is the same.** Any new build wipes it. An editor that flashes should back up the layout before flashing and restore it after.
- **Pipe gotcha in shell tooling:** `cmd | grep -q` under `pipefail` gives false "not found" (the left side dies of SIGPIPE). Relevant if the app shells out to tools.

## Bigger ideas (brainstorm, not planned)

- **Context-generated keys:** an LLM picks 16 actions for the current app. It must choose from a fixed list of approved actions and never write commands that run.
- **A layout that learns from your shortcut usage:** count only shortcuts that include modifiers, and store counts locally.
- **A hover-aware knob:** the knob controls whatever is under the mouse, using Windows UI Automation. Support varies by app.
- **Stream frames to the OLED:** for example an audio visualizer. Watch for burn-in.
- **Push-to-talk dictation** with a local speech-to-text model.
- **One pad controlling several PCs** over the network. It needs authentication.
- **A force-feedback knob** (SmartKnob-style). That's a hardware project.
