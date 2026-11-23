#!/usr/bin/env python3
"""Back up the pad's VIA layout and put the user's edits back after a flash.

  tools/via-layout.py backup              read the pad into via/layout.json
  tools/via-layout.py restore             reset to the build's defaults, then reapply edits
  tools/via-layout.py diff                show the pad's edits against its build's defaults
  tools/via-layout.py apply SLOT...       copy slots (or "macros") from the backup to the pad
  tools/via-layout.py set SLOT KEYCODE    set one slot, e.g. set "L8 key16" 0x0173

tools/flash-pad.sh runs backup before flashing and restore after. Slots are
named like "L3 key6", "L1 knob-big", "L2 enc0 cw". The merge rules are in
via_merge.py; the design is docs/superpowers/specs/2026-11-23-via-layout-backup-design.md.

It talks VIA's raw HID protocol through hidapitester.exe (see flash-pad.sh),
batching many commands into one call.
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from via_merge import MergeResult, Slots, differences, merge, merge_macros  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WIN_TOOLS = os.environ.get("KB16_WIN_TOOLS", "/mnt/c/Tools/kb16-flash")
HID = os.environ.get("KB16_HID_TOOL", f"{WIN_TOOLS}/hidapitester.exe")
PAD_FILTER = ["--vidpid", "D010/1601", "--usagePage", "0xFF60", "--usage", "0x61"]

# KB16 shape. VIA can't report these, so they're set here; the layer count and
# macro buffer size are read from the pad.
ROWS, COLS, ENCODERS = 4, 5, 3
KNOBS = {0: "knob-left", 1: "knob-right", 2: "knob-big"}  # presses, column 4

REPORT = 32   # VIA report size
CHUNK = 28    # max bytes per VIA buffer command
BATCH = 40    # commands per hidapitester call, well under Windows' command-line limit

# VIA command IDs (quantum/via.h)
SET_KEYCODE, KEYMAP_RESET, MACRO_SIZE, MACRO_GET, MACRO_SET = 0x05, 0x06, 0x0D, 0x0E, 0x0F
LAYER_COUNT, KEYMAP_GET, ENC_GET, ENC_SET = 0x11, 0x12, 0x14, 0x15
FLASH_TOOLS = 0xF0  # this firmware's own commands; F0 01 = build ID


class Fail(Exception):
    pass


# ---------------------------------------------------------------- transport

def parse_replies(text: str, cmds: list[list[int]]) -> list[list[int]]:
    """Split hidapitester output into one REPORT-byte reply per command."""
    tokens = [int(t, 16) for t in re.findall(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{2}(?![0-9A-Fa-f])", text)]
    for size in (REPORT + 1, REPORT):   # hidapitester may print the extra byte of --length 33
        if len(tokens) == size * len(cmds):
            replies = [tokens[i * size:i * size + REPORT] for i in range(len(cmds))]
            break
    else:
        raise Fail(f"expected {len(cmds)} replies from the pad, got {len(tokens)} bytes")
    for cmd, reply in zip(cmds, replies):
        if reply[0] != cmd[0]:
            raise Fail(f"the pad answered command {cmd[0]:#04x} with {reply[0]:#04x} (is the VIA app open?)")
    return replies


class HidPad:
    def run(self, cmds: list[list[int]]) -> list[list[int]]:
        replies = []
        for i in range(0, len(cmds), BATCH):
            batch = cmds[i:i + BATCH]
            args = [HID, "-q", *PAD_FILTER, "--open", "--length", str(REPORT + 1), "--timeout", "1000"]
            for c in batch:
                args += ["--send-output", ",".join(["0"] + [f"{b:#04x}" for b in c]), "--read-input"]
            args.append("--close")
            try:
                out = subprocess.run(args, capture_output=True, text=True, timeout=60).stdout
            except (OSError, subprocess.TimeoutExpired) as e:
                raise Fail(f"couldn't run hidapitester: {e}")
            replies += parse_replies(out, batch)
        return replies


# ---------------------------------------------------------------- layout

@dataclass
class Layout:
    build: str
    shape: dict          # layers, rows, cols, encoders, macro_size
    slots: Slots
    macros: bytes = field(default=b"")


@dataclass
class Files:
    dir: Path

    @property
    def layout(self) -> Path:
        return self.dir / "layout.json"

    @property
    def defaults(self) -> Path:
        return self.dir / "defaults.json"


def key_name(row: int, col: int) -> str:
    if col < 4:
        return f"key{row * 4 + col + 1}"
    return KNOBS.get(row, f"r{row}c{col}") if col == 4 else f"r{row}c{col}"


def enc_name(enc: int, cw: int) -> str:
    return f"enc{enc} {'cw' if cw else 'ccw'}"


def addresses(layers: int) -> dict[str, tuple]:
    """Slot name -> ("key", layer, row, col) or ("enc", layer, encoder, cw)."""
    out = {}
    for l in range(layers):
        for r in range(ROWS):
            for c in range(COLS):
                out[f"L{l + 1} {key_name(r, c)}"] = ("key", l, r, c)
        for e in range(ENCODERS):
            for cw in (0, 1):
                out[f"L{l + 1} {enc_name(e, cw)}"] = ("enc", l, e, cw)
    return out


def chunks(total: int):
    for off in range(0, total, CHUNK):
        yield off, min(CHUNK, total - off)


def read_build(pad) -> str:
    reply = pad.run([[FLASH_TOOLS, 0x01]])[0]
    if reply[1] != 0x01:
        raise Fail("the pad didn't report its build ID")
    return bytes(reply[2:]).split(b"\0")[0].decode()


def read_layout(pad) -> Layout:
    build = read_build(pad)
    head = pad.run([[LAYER_COUNT], [MACRO_SIZE]])
    layers, macro_size = head[0][1], head[1][1] << 8 | head[1][2]

    key_bytes = layers * ROWS * COLS * 2
    key_cmds = [[KEYMAP_GET, off >> 8, off & 0xFF, n] for off, n in chunks(key_bytes)]
    enc_cmds = [[ENC_GET, l, e, cw] for l in range(layers) for e in range(ENCODERS) for cw in (0, 1)]
    mac_cmds = [[MACRO_GET, off >> 8, off & 0xFF, n] for off, n in chunks(macro_size)]
    replies = pad.run(key_cmds + enc_cmds + mac_cmds)

    keybuf = bytes(b for c, r in zip(key_cmds, replies) for b in r[4:4 + c[3]])
    slots = {}
    for name, (kind, l, a, b) in addresses(layers).items():
        if kind == "key":
            i = ((l * ROWS + a) * COLS + b) * 2
            slots[name] = keybuf[i] << 8 | keybuf[i + 1]
    enc_replies = replies[len(key_cmds):len(key_cmds) + len(enc_cmds)]
    for c, r in zip(enc_cmds, enc_replies):
        slots[f"L{c[1] + 1} {enc_name(c[2], c[3])}"] = r[4] << 8 | r[5]
    mac_replies = replies[len(key_cmds) + len(enc_cmds):]
    macros = bytes(b for c, r in zip(mac_cmds, mac_replies) for b in r[4:4 + c[3]])

    shape = {"layers": layers, "rows": ROWS, "cols": COLS, "encoders": ENCODERS, "macro_size": macro_size}
    return Layout(build, shape, slots, macros)


def write_slots(pad, slots: Slots) -> None:
    addr = addresses(256)
    cmds = []
    for name, kc in slots.items():
        if name not in addr:
            raise Fail(f"no slot named {name!r} (examples: 'L3 key6', 'L1 knob-big', 'L2 enc0 cw')")
        kind, l, a, b = addr[name]
        cmds.append([SET_KEYCODE if kind == "key" else ENC_SET, l, a, b, kc >> 8, kc & 0xFF])
    if cmds:
        pad.run(cmds)


def write_macros(pad, buf: bytes) -> None:
    pad.run([[MACRO_SET, off >> 8, off & 0xFF, n, *buf[off:off + n]] for off, n in chunks(len(buf))])


# ---------------------------------------------------------------- files

def to_json(layout: Layout) -> dict:
    layers = []
    for l in range(layout.shape["layers"]):
        prefix = f"L{l + 1} "
        keys = {n[len(prefix):]: f"0x{v:04X}" for n, v in layout.slots.items()
                if n.startswith(prefix) and not n[len(prefix):].startswith("enc")}
        turns = {n[len(prefix):]: f"0x{v:04X}" for n, v in layout.slots.items()
                 if n.startswith(prefix) and n[len(prefix):].startswith("enc")}
        layers.append({"keys": keys, "turns": turns})
    return {"build": layout.build, "shape": layout.shape, "layers": layers,
            "macros": layout.macros.rstrip(b"\0").hex()}


def from_json(d: dict) -> Layout:
    slots = {}
    for l, layer in enumerate(d["layers"]):
        for part in ("keys", "turns"):
            for n, v in layer[part].items():
                slots[f"L{l + 1} {n}"] = int(v, 16)
    macros = bytes.fromhex(d["macros"]).ljust(d["shape"]["macro_size"], b"\0")
    return Layout(d["build"], d["shape"], slots, macros)


def load(path: Path) -> Layout | None:
    return from_json(json.loads(path.read_text())) if path.exists() else None


def save(path: Path, layout: Layout) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_json(layout), indent=1) + "\n")


# ---------------------------------------------------------------- commands

def backup(pad, files: Files) -> Layout:
    layout = read_layout(pad)
    save(files.layout, layout)
    return layout


@dataclass
class RestoreResult:
    restored: bool                       # False: no defaults record for the backup's build
    merge: MergeResult | None = None
    macros_restored: bool = False
    differences: list[str] = field(default_factory=list)
    backup_build: str = ""


def restore(pad, files: Files) -> RestoreResult:
    """Reset the pad to its build's defaults, then put the backup's edits on top.

    Always resets first: QMK only wipes VIA's storage when the build *day*
    changes, so after a same-day flash the pad still holds the old layout and
    the new defaults would otherwise never load.
    """
    saved = load(files.layout)
    old = load(files.defaults)
    pad.run([[KEYMAP_RESET]])
    new = read_layout(pad)

    if saved is None or old is None or old.build != saved.build:
        result = RestoreResult(False, backup_build=saved.build if saved else "")
        if saved:
            result.differences = differences(saved.slots, new.slots)
            if saved.macros.rstrip(b"\0"):
                result.differences.append("macros")
        save(files.defaults, new)
        return result

    m = merge(old.slots, saved.slots, new.slots)
    try:
        macros = merge_macros(saved.macros, new.shape["macro_size"])
    except ValueError as e:
        raise Fail(f"{e}; nothing was restored")
    write_slots(pad, {s: v for s, v in m.merged.items() if new.slots.get(s) != v})
    if macros is not None and macros != new.macros:
        write_macros(pad, macros)

    check = read_layout(pad)
    if check.slots != m.merged or (macros is not None and check.macros != macros):
        bad = differences(check.slots, m.merged)
        raise Fail(f"the pad didn't keep the restored layout ({', '.join(bad) or 'macros'})")
    save(files.defaults, new)
    save(files.layout, check)   # so a rerun finds a matching record and is a no-op
    return RestoreResult(True, m, macros is not None, backup_build=saved.build)


def apply(pad, files: Files, names: list[str]) -> None:
    saved = load(files.layout)
    if saved is None:
        raise Fail("no backup in via/layout.json")
    missing = [n for n in names if n != "macros" and n not in saved.slots]
    if missing:
        raise Fail(f"not in the backup: {', '.join(missing)}")
    write_slots(pad, {n: saved.slots[n] for n in names if n != "macros"})
    if "macros" in names:
        write_macros(pad, saved.macros[:read_layout(pad).shape["macro_size"]])


def set_slot(pad, name: str, keycode: int) -> None:
    write_slots(pad, {name: keycode})


def edits_now(pad, files: Files) -> tuple[Layout, Layout | None]:
    now = read_layout(pad)
    old = load(files.defaults)
    return now, old if old and old.build == now.build else None


# ---------------------------------------------------------------- CLI

def kc(v: int) -> str:
    return f"0x{v:04X}"


def main(argv: list[str]) -> int:
    files = Files(ROOT / "via")
    pad = HidPad()
    cmd = argv[0] if argv else ""
    try:
        if cmd == "backup":
            layout = backup(pad, files)
            print(f"Saved the pad's layout (build {layout.build}) to via/layout.json")
        elif cmd == "restore":
            r = restore(pad, files)
            if r.restored:
                m = r.merge
                print(f"Restored {len(m.edits)} edit(s) from build {r.backup_build}"
                      + (", plus macros" if r.macros_restored else "") + ":")
                for s in sorted(m.edits):
                    print(f"  {s}: {kc(m.edits[s])}")
                for c in m.conflicts:
                    print(f"  CONFLICT {c.slot}: kept your {kc(c.kept)}; new default {kc(c.new_default)} not applied")
                for s in m.dropped:
                    print(f"  DROPPED {s}: the new build has no such slot")
            elif r.backup_build:
                print(f"No defaults record for build {r.backup_build}, so edits can't be told apart from")
                print("old defaults. The pad now has the new build's defaults. Nothing was restored.")
                if r.differences:
                    print("The backup differs from the new defaults in:")
                    for s in r.differences:
                        print(f"  {s}")
                    print('To put any back: tools/via-layout.py apply "L3 key6" ...')
                else:
                    print("The backup matches the new defaults, so nothing is lost.")
            else:
                print("No backup yet; recorded this build's defaults.")
        elif cmd == "diff":
            now, old = edits_now(pad, files)
            if old is None:
                print(f"No defaults record for build {now.build}; the next flash makes one.")
            else:
                diffs = differences(old.slots, now.slots)
                for s in diffs:
                    print(f"  {s}: {kc(now.slots[s])} (default {kc(old.slots[s])})")
                if now.macros.rstrip(b"\0"):
                    print("  macros: set")
                if not diffs and not now.macros.rstrip(b"\0"):
                    print("No edits: the pad matches its build's defaults.")
        elif cmd == "apply" and len(argv) > 1:
            apply(pad, files, argv[1:])
            print(f"Applied from the backup: {', '.join(argv[1:])}")
        elif cmd == "set" and len(argv) == 3:
            set_slot(pad, argv[1], int(argv[2], 0))
            print(f"Set {argv[1]} to {kc(int(argv[2], 0))}")
        else:
            print(__doc__.strip().split("\n\n")[1])
            return 2
    except Fail as e:
        print(f"FAILED: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
