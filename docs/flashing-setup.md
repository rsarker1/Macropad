# One-time setup for automatic flashing

After this, `tools/flash-pad.sh` flashes the pad from WSL with no hands on it.

## 1. Get the two Windows tools

Both go in `C:\Tools\kb16-flash\`. To use another folder, set `KB16_WIN_TOOLS` to its WSL path, such as `/mnt/d/tools/kb16`.

- **hidapitester:** download the Windows build from the releases page of `github.com/todbot/hidapitester` and put `hidapitester.exe` in the folder.
- **dfu-util:** download the latest `dfu-util-*-binaries.tar.xz` from `dfu-util.sourceforge.net/releases/`. It's easiest to extract it in WSL:

  ```bash
  mkdir -p /mnt/c/Tools/kb16-flash
  tar -xf ~/Downloads/dfu-util-*-binaries.tar.xz      # wherever you saved it
  cp dfu-util-*-binaries/win64/* /mnt/c/Tools/kb16-flash/
  ```

  Copy everything in `win64`, not just `dfu-util.exe`, since it may need the DLLs next to it.

You don't need new drivers. The ones QMK Toolbox installed already cover the bootloader.

## 2. Flash the new firmware once by hand

The firmware on your pad now doesn't have the reboot command yet. Flash `doio_kb16_rev2_enhanced.bin` from this repo the usual way, once: hold the top-left key while plugging in, wait for QMK Toolbox's yellow line, then open the file and flash it.

## 3. Check it works

```bash
tools/flash-pad.sh --check
```

`Pad:` should say `connected, running <date>`, with the same date as `Repo .bin:`. From now on, `tools/flash-pad.sh` handles everything.

## What to expect when flashing

After the download, the pad's bootloader waits for a USB reset before it starts the new build, and `dfu-util` can't send one on Windows. The script then restarts the pad's USB device through Windows, which needs admin rights: **a UAC prompt appears, and clicking Yes is the only hands-on step.** If you decline it or don't answer within 2 minutes, the script asks you to unplug and replug the pad (no key held).

If anything else fails, the script prints how to recover by hand: hold the top-left key while plugging in, then rerun the script. It notices when the pad is already in the bootloader.
