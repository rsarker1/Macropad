# Feature backlog

Ideas from planning with Rahul. Each notes the catch that came up in discussion. Status is as of 2026-11-23. Rahul chooses what gets built, so treat these as options, not a queue.

**How it's organized:** by what a feature changes (firmware, script, or firmware plus PC tooling), and within each section by payoff, highest first. Ideas marked ⏸ are on the backburner (see the rule below).

**Backburner rule (Rahul, 2026-11-23):** anything that needs raw HID in both directions waits until a working version of the companion app is live. That means the AutoHotkey script talking raw HID, or the pad sending messages on its own. Request-and-reply from a PC tool through `hidapitester.exe` already works (`hid_cmd` in `tools/flash-pad.sh`, proven on every flash), so ideas that only need that stay active.

**Top three overall:** VIA layout backup, per-app actions, knob-held shift layer.

## Already built

- **Color and effect per layer.**
- **Layer knob hold-and-turn.**
- **Jump straight to a layer:** hold the layer knob and press key 1–8.
- **Knob labels on the OLED.**
- **Automatic flashing** with build-ID verification (`tools/flash-pad.sh`; one UAC click, no replug).
- **Exact-timing LED driver** (`ws2812_custom.c`), which fixed random colors during fades.

For how each one works, see `README.md` and `CLAUDE.md`.

## Firmware

1. **Knob-held shift layer.**
   - **What:** hold the right knob (its press is unassigned) and every key sends a modifier plus its F-key, such as `Ctrl+F13`.
   - **Why it works:** Rahul's keyboard can't send F13–F24, so any modifier with F13–F24 is pad-only too. That doubles the pad-only shortcuts, with no delay on taps. The script gets new actions to match.
   - **Avoid:** `Ctrl+Alt+Shift+F13`–`F20`, which are the announce combos.
2. **Knob acceleration.**
   - **What:** spinning faster takes bigger steps.
   - **Catch:** apply it only to volume and scrolling. Undo/Redo and zoom must stay one step at a time.
3. **Timer or Pomodoro.**
   - **What:** a key starts it, the OLED counts down, and the 16 LEDs empty one by one as a progress bar, then flash at zero.
   - **Catch:** it covers the layer colors while it runs, unless it uses only one row.
4. **On-pad macro recorder** (QMK dynamic macros).
   - **What:** record a keystroke sequence into a key and replay it, with no VIA and no reflash.
   - **Catch:** recordings live in RAM and are lost when the pad is unplugged.
5. **Combos.**
   - **What:** pressing two keys together sends a third pad-only shortcut.
   - **Catch:** a short delay on the keys involved, so use only pairs never pressed together otherwise.
6. **Tap vs hold on specific keys.**
   - **Catch:** every tap waits about 200 ms to see if it becomes a hold. Use it only on keys like app launchers, never on media, navigation or Delete. The shift layer (#1) covers most of the same need with no delay.
7. **Hold a knob and turn it** for a second function on each knob.
   - **Catch:** more to remember about which knobs behave how.
8. **Dim the LEDs when idle**, after a few minutes without input, as the OLED already turns off after 60 s.

## Script (AutoHotkey)

1. **Per-app actions with `#HotIf WinActive(...)`.**
   - **What:** the same pad key does different things depending on the focused app.
   - **Why it's cheap:** layers 2–8 all send identical F-keys, so the firmware layer is effectively a page number that the script reads. App awareness can live entirely in the script, with no firmware change.
2. **Focus or launch.** App keys switch to the app's window if it's already open, instead of opening a second copy.
3. **Actions in a config file** (INI or JSON) that reloads automatically when it changes.
   - **Why:** remapping keys wouldn't require editing code. It pays off more as the number of actions grows, so build it before they multiply.
4. **Meeting layer.** Mute, camera and leave, each sent to whichever of Teams, Zoom or Discord is running.
5. **Move windows between monitors and arrange layouts.**
   - **Why:** Rahul plans a desk with a 55" TV above a 27" monitor and a small 15.6" monitor on the left. Low priority until that desk exists.
6. **Clipboard history layer.** Keys 5–16 paste the last 12 clipboard items, and Info shows a preview of each.
7. **Text snippets:** signatures, canned replies, today's date.
8. **Push-to-talk dictation** with a local speech-to-text model. The most work in this section.
9. **A hover-aware knob.**
   - **What:** the knob controls whatever is under the mouse, using Windows UI Automation.
   - **Catch:** the knob must first send pad-only keys, so it also needs a small firmware change. Support varies by app.

## Firmware plus PC tooling (request-and-reply, works today)

1. **Keep the VIA layout across flashes.**
   - **What:** `flash-pad.sh` reads the layout, knob turns and macros through VIA's own protocol before flashing, and writes them back after. No firmware change.
   - **Catch:** writing an old layout back would silently undo new defaults in `keymap.c`. It needs a rule, such as restoring only when asked, or only when the layout's shape is unchanged.
2. **Claude Code status light.**
   - **What:** a new `F0 03` subcommand sets one key's LED color. Claude Code hooks call `hidapitester.exe` to light it while Claude waits for input, and clear it when done. It's the first slice of the agent approval pad.
   - **Catch:** the per-layer lighting redraws every LED on each layer change, so the status key needs to be drawn on top (in `rgb_matrix_indicators_user`) to survive.
3. **Key usage counts, then a layout that learns.**
   - **What:** the firmware counts presses per key and layer and saves them on the pad; a tool reads them. Later, combine them with the script's action history to suggest moves ("key 14 gets 40 presses a day, move it to key 2").
   - **Catch:** saving counts writes to flash-emulated EEPROM, which wears out, so batch the writes (for example, once every few minutes).

## ⏸ Backburner: needs raw HID in both directions

These wait for the companion app. Raw HID is the two-way USB data channel VIA already uses. New firmware features become subcommands under `0xF0` (see `CLAUDE.md`).

- **Unverified first step:** whether AutoHotkey can receive pad messages through Windows Raw Input (`WM_INPUT`, usage page `0xFF60`, usage `0x61`), and whether sending through `hidapi.dll` with `DllCall` is practical. If it's painful, that argues for the companion app over growing the script.
- **A 4×4 grid of key labels on the OLED.** Each label can be 5 characters, since 21 ÷ 4 leaves room for 5. The PC sends them from its action table.
- **Replace the announce combos with real messages,** so no hidden keystrokes can leak into apps.
- **Switch layers automatically by app.** It only works well with all four of these rules:
  1. Switch only when the focused app changes, not on every focus event.
  2. Debounce, so quick Alt-Tabs and pop-ups don't flip the layer.
  3. Switch only for apps on a list.
  4. A manual layer choice holds until the app changes.

  Without the OLED label grid, Rahul loses track of what the keys do, so build the grid first.
- **Status lights driven by the PC,** for example a key that turns red when the mic is muted.
- **Report knob events to the PC** ("knob 3 turned right, sent Ctrl+Z") while still sending the real key. Rahul chose OLED labels instead, for now.
- **PC tells the pad to change layer** or what text to show.
- **A tiny mixer.** Pressing the right knob cycles through apps playing sound, the OLED shows the app's name and volume, and the big knob sets it. It replaces today's focused-app volume.
- **OLED pages.** The right knob press flips between the layer, now playing, a clock, CPU and GPU temperature, and Claude Code status.
- **Green or red feedback on each key press,** so failed actions (such as a missing SoundVolumeView) stop being silent.
- **Layer names on the OLED,** such as `LAYER 3: EDIT`.
- **A CI build light** for the current repo.
- **The pad as a status console:** the app owns all 16 LEDs and the screen, and ranks approvals, CI, meetings and timers by urgency.
- **Context-generated keys:** an LLM picks 16 actions for the current app. It must choose from a fixed list of approved actions and never write commands that run.
- **Stream frames to the OLED,** for example an audio visualizer. Watch for burn-in.
- **One pad controlling several PCs** over the network. It needs authentication.

## Dropped

- **Scripts that run on the pad (Lua):** the STM32F103 has 20 KB of RAM, and Lua alone takes most of it.
- **A force-feedback knob** (SmartKnob-style): that's a hardware project, not firmware or script.

## Long-term: companion app and agent approval pad

Rahul is considering a bigger project to replace AutoHotkey with a companion app (Python or Go) that talks to the pad over raw HID. It's what lifts the backburner. The first slice is an **approval panel for AI coding agents**:

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
- **Module or fork:** prefer QMK community modules over forking QMK (Vial maintains a fork). Catch: modules have no raw HID or VIA command hook, so custom `0xF0` commands can't be a clean module today. Asking QMK for that hook may avoid a fork.
