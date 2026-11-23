#!/usr/bin/env bash
# Flash the KB16 from WSL with no hands on the pad.
#
#   tools/flash-pad.sh           flash doio_kb16_rev2_enhanced.bin (must be committed)
#   tools/flash-pad.sh --check   report what's connected and which build is running; flashes nothing
#   tools/flash-pad.sh --skip-layout   flash without saving and restoring the VIA layout
#
# How it works: the firmware answers a raw HID command with its build ID and
# reboots into the bootloader on request (see "Flash tools" in keymap.c). The
# script drives two Windows programs through WSL interop:
#   hidapitester.exe  talks raw HID to the running firmware
#   dfu-util.exe      flashes the bootloader (stm32duino, USB ID 1EAF:0003)
# Both live in KB16_WIN_TOOLS (default /mnt/c/Tools/kb16-flash). If the
# bootloader then sits waiting to start the new build, the script restarts its
# USB device with Windows' pnputil, which shows one UAC prompt.
#
# Around the flash, tools/via-layout.py saves the VIA layout to via/layout.json
# and afterwards puts the user's edits back on top of the new build's defaults.
# Exit code 0 means the pad is running exactly the build in the .bin, with the
# layout restored.

set -euo pipefail

ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
BIN="$ROOT/doio_kb16_rev2_enhanced.bin"
WIN_TOOLS="${KB16_WIN_TOOLS:-/mnt/c/Tools/kb16-flash}"
HID="${KB16_HID_TOOL:-$WIN_TOOLS/hidapitester.exe}"
DFU="${KB16_DFU_TOOL:-$WIN_TOOLS/dfu-util.exe}"
PNPUTIL="/mnt/c/Windows/System32/pnputil.exe"
VIA_LAYOUT="$ROOT/tools/via-layout.py"

PAD_FILTER=(--vidpid D010/1601 --usagePage 0xFF60 --usage 0x61)
DFU_ID="1EAF:0003"
BOOT_WAIT=15     # seconds to wait for the bootloader to appear
RETURN_WAIT=20   # seconds to wait for the pad to come back after flashing

say()  { printf '%s\n' "$*"; }
fail() {
    say "FAILED: $*"
    say ""
    say "Manual recovery (ask Rahul):"
    say "  1. Unplug the pad. Hold the top-left key and plug it back in."
    say "  2. QMK Toolbox should show a yellow 'STM32Duino device connected' line."
    say "  3. Then rerun tools/flash-pad.sh (it detects a pad already in the bootloader),"
    say "     or flash $(basename "$BIN") from QMK Toolbox."
    exit 1
}

# The download worked, but the bootloader is still waiting to start the new
# build. Bootmagic would only put it back into the bootloader, so: plain replug.
stuck_in_bootloader() {
    say "FAILED: build $EXPECTED is written, but the pad is still in the bootloader waiting to start it."
    say ""
    say "Ask Rahul to unplug the pad and plug it back in, without holding any key."
    say "Then run tools/flash-pad.sh --check to confirm it's running $EXPECTED."
    exit 1
}

# After a download, the stm32duino bootloader starts the new build only after a
# USB reset. dfu-util's -R can't send a real one on Windows (WinUSB), but
# restarting the device does. pnputil needs admin for that, so this shows a
# UAC prompt; declining it, or no answer within 2 minutes, returns non-zero.
bootloader_instance() {  # Windows device ID of the connected bootloader, or nothing
    local vid="${DFU_ID%%:*}" pid="${DFU_ID##*:}"
    "$PNPUTIL" /enum-devices /connected 2>/dev/null | tr -d '\r' |
        grep -io "USB\\\\VID_${vid}&PID_${pid}\\\\[^[:space:]]*" | head -1 || true
}

restart_bootloader() {
    local id
    id="$(bootloader_instance)"
    [[ -n "$id" ]] || return 1
    say "Restarting the bootloader's USB device: click Yes on the Windows UAC prompt..."
    timeout 120 powershell.exe -NoProfile -Command \
        "\$p = Start-Process pnputil.exe -ArgumentList '/restart-device','\"$id\"' -Verb RunAs -Wait -PassThru -WindowStyle Hidden; exit \$p.ExitCode" \
        >/dev/null 2>&1
}

need_tools() {
    for t in "$HID" "$DFU"; do
        [[ -f "$t" ]] || { say "Missing $t"; say "See docs/flashing-setup.md for the one-time setup."; exit 2; }
    done
}

# Send one 32-byte raw HID report (leading 0 = no report ID) and print the
# reply as space-separated uppercase hex bytes. Prints nothing on failure.
hid_cmd() {
    "$HID" -q "${PAD_FILTER[@]}" --open --length 33 --send-output "0,$1" \
        --timeout 1000 --read-input --close 2>/dev/null |
        tr -s ' \r\n\t' '\n' | grep -E '^[0-9A-Fa-f]{2}$' | tr 'a-f' 'A-F' | tr '\n' ' ' || true
}

# Pipe checks use `grep >/dev/null`, not `grep -q`: -q stops reading at the
# first match, the tool on the left then dies of SIGPIPE (exit 141), and
# pipefail turns a found device into "not found".
pad_present()   { "$HID" "${PAD_FILTER[@]}" --list 2>/dev/null | grep -i 'D010/1601' >/dev/null; }
in_bootloader() { "$DFU" -l 2>/dev/null | grep -i "${DFU_ID}" >/dev/null; }

# Build ID the running firmware reports, e.g. 2026-11-22-22:11:29. Empty if none.
pad_build_id() {
    hid_cmd "0xF0,0x01" | python3 -c '
import sys
b = sys.stdin.read().split()
for i in range(len(b) - 1):
    if b[i] == "F0" and b[i + 1] == "01":
        out = []
        for h in b[i + 2:]:
            if h == "00":
                break
            out.append(chr(int(h, 16)))
        print("".join(out))
        break
'
}

# Build ID baked into the .bin.
bin_build_id() { grep -a -o 'KB16ID:[0-9][0-9:-]\{18\}' "$BIN" | head -1 | cut -d: -f2-; }

wait_for() {  # wait_for <seconds> <command...>
    local deadline=$((SECONDS + $1)); shift
    until "$@"; do (( SECONDS < deadline )) || return 1; sleep 0.5; done
}

running_matches() { [[ "$(pad_build_id)" == "$EXPECTED" ]]; }

# After the download: 0 = the new build is running, 1 = the bootloader is
# holding the pad, 2 = neither showed up within a minute. The bootloader also
# shows up briefly during a normal start, so it must still be there 3 s later.
after_download() {
    local deadline=$((SECONDS + 60))
    while (( SECONDS < deadline )); do
        running_matches && return 0
        if [[ -n "$(bootloader_instance)" ]]; then
            sleep 3
            running_matches && return 0
            [[ -n "$(bootloader_instance)" ]] && return 1
        fi
        sleep 1
    done
    return 2
}

# ---------------------------------------------------------------- --check
if [[ "${1:-}" == "--check" ]]; then
    need_tools
    say "Tools:      $WIN_TOOLS"
    if [[ -f "$BIN" ]]; then
        c="$(git -C "$ROOT" log -1 --format=%h -- "$BIN" 2>/dev/null)"
        [[ -n "$(git -C "$ROOT" status --porcelain -- "$BIN")" ]] && c="${c:+$c + }uncommitted changes"
        say "Repo .bin:  $(bin_build_id) (${c:-not committed})"
    else
        say "Repo .bin:  missing"
    fi
    if in_bootloader; then
        say "Pad:        in the bootloader, waiting for a flash"
    elif pad_present; then
        id="$(pad_build_id)"
        say "Pad:        connected, running ${id:-a build without the flash-tools command (flash it once manually)}"
    else
        say "Pad:        not found"
    fi
    exit 0
fi

# ---------------------------------------------------------------- flash
SKIP_LAYOUT=0
[[ "${1:-}" == "--skip-layout" ]] && SKIP_LAYOUT=1
need_tools
[[ -f "$BIN" ]] || { say "No $(basename "$BIN"). Build first."; exit 2; }

# Rule: whatever is on the pad must match a commit.
if ! git -C "$ROOT" ls-files --error-unmatch "$BIN" >/dev/null 2>&1 ||
   [[ -n "$(git -C "$ROOT" status --porcelain -- "$BIN" keyboards)" ]]; then
    say "The .bin or firmware source has uncommitted changes. Commit them, then flash."
    exit 2
fi

EXPECTED="$(bin_build_id)"
[[ -n "$EXPECTED" ]] || { say "The .bin has no KB16ID build ID, so its flash can't be verified."; exit 2; }
COMMIT="$(git -C "$ROOT" log -1 --format=%h -- "$BIN")"
say "Flashing build $EXPECTED (commit $COMMIT)"

# Windows programs read Windows paths most reliably, so stage the file next to the tools.
cp "$BIN" "$WIN_TOOLS/kb16-flash.bin"
WIN_BIN="$(wslpath -w "$WIN_TOOLS/kb16-flash.bin")"
DFU_ARGS=(-d "$DFU_ID" -a 2 -R -D "$WIN_BIN")

DFU_LOG="$(mktemp)"
trap 'rm -f "$DFU_LOG"' EXIT

# Work out the pad's state before anything grabs the USB device.
if in_bootloader; then
    say "Pad is already in the bootloader."
    if (( ! SKIP_LAYOUT )); then
        say "Its VIA layout can't be read from there. After the flash, the last backup is used:"
        say "  via/layout.json, from build $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["build"])' "$ROOT/via/layout.json" 2>/dev/null || echo 'none')"
    fi
    timeout 60 "$DFU" "${DFU_ARGS[@]}" >"$DFU_LOG" 2>&1 || true   # a stuck bootloader can make it hang
elif pad_present; then
    if (( ! SKIP_LAYOUT )); then
        python3 "$VIA_LAYOUT" backup || {
            say "Not flashing: the VIA layout couldn't be saved, and flashing would wipe it."
            say "To flash anyway and lose it, rerun with --skip-layout."
            exit 2
        }
    fi

    # The bootloader may only wait briefly after a reset, so when dfu-util
    # supports --wait, start it first and let it catch the device the moment
    # it appears. Otherwise poll for the bootloader, then flash.
    # Use -w, not --wait: dfu-util 0.11's long --wait wrongly takes a value,
    # so it swallows the -d after it ("Unexpected argument: 1EAF:0003").
    DFU_PID=""
    if "$DFU" --help 2>&1 | grep -- '--wait' >/dev/null; then
        timeout $((BOOT_WAIT + 60)) "$DFU" -w "${DFU_ARGS[@]}" >"$DFU_LOG" 2>&1 &
        DFU_PID=$!
        sleep 1
    fi

    reply="$(hid_cmd "0xF0,0x02,0x42,0x4F,0x4F,0x54")"   # F0 02 'B' 'O' 'O' 'T'
    if [[ "$reply" != *"F0 02 01"* ]]; then
        [[ -n "$DFU_PID" ]] && kill "$DFU_PID" 2>/dev/null || true
        fail "the pad didn't accept the reboot command (reply: '${reply:-none}'). It's probably running firmware from before the flash tools were added."
    fi
    say "Pad is rebooting into the bootloader..."

    if [[ -n "$DFU_PID" ]]; then
        wait "$DFU_PID" || true
    else
        wait_for "$BOOT_WAIT" in_bootloader || fail "the bootloader never appeared."
        timeout 60 "$DFU" "${DFU_ARGS[@]}" >"$DFU_LOG" 2>&1 || true   # a stuck bootloader can make it hang
    fi
else
    fail "pad not found. Is it plugged in?"
fi

cat "$DFU_LOG"
grep -q 'Download done' "$DFU_LOG" || fail "dfu-util didn't finish the download (log above)."

say "Waiting for the pad to restart..."
state=0
after_download || state=$?
if (( state == 1 )); then
    restart_bootloader || stuck_in_bootloader
    wait_for "$RETURN_WAIT" running_matches || stuck_in_bootloader
elif (( state == 2 )); then
    fail "the pad didn't come back running build $EXPECTED (it reports '$(pad_build_id)')."
fi

say "OK: pad is running build $EXPECTED (commit $COMMIT)."

if (( ! SKIP_LAYOUT )); then
    python3 "$VIA_LAYOUT" restore || {
        say "The flash worked, but the VIA layout wasn't restored. The backup is in via/layout.json;"
        say "run tools/via-layout.py restore to try again."
        exit 3
    }
    say "Commit via/ so the layout and this build's defaults are recorded."
fi
