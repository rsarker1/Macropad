import importlib.util
import tempfile
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location("via_layout", Path(__file__).with_name("via-layout.py"))
vl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vl)

# Real hidapitester output for: 0x11 (layer count), 0x0D (macro size).
REAL_OUTPUT = """ 11 08 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
 00
 0D 02 37 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
 00
"""


class FakePad:
    """Emulates the VIA commands via-layout.py uses, on an in-memory pad."""

    def __init__(self, build, defaults_keys, defaults_enc, layers=2, macro_size=40):
        self.build, self.layers, self.macro_size = build, layers, macro_size
        self.flash_keys, self.flash_enc = dict(defaults_keys), dict(defaults_enc)
        self.keys, self.enc = dict(defaults_keys), dict(defaults_enc)
        self.macros = bytearray(macro_size)

    def flash(self, build, keys, enc):  # a new build; VIA storage kept, as on a same-day build
        self.build, self.flash_keys, self.flash_enc = build, dict(keys), dict(enc)

    def run(self, cmds):
        out = []
        for c in cmds:
            r = list(c) + [0] * (32 - len(c))
            op = c[0]
            if op == 0xF0:
                b = self.build.encode()
                r[2:2 + len(b)] = b
            elif op == 0x11:
                r[1] = self.layers
            elif op == 0x0D:
                r[1], r[2] = self.macro_size >> 8, self.macro_size & 0xFF
            elif op == 0x06:
                self.keys, self.enc = dict(self.flash_keys), dict(self.flash_enc)
            elif op == 0x12:
                off, n = c[1] << 8 | c[2], c[3]
                buf = self._keybuf()
                r[4:4 + n] = buf[off:off + n]
            elif op == 0x05:
                self.keys[(c[1], c[2], c[3])] = c[4] << 8 | c[5]
            elif op == 0x14:
                kc = self.enc.get((c[1], c[2], c[3]), 0)
                r[4], r[5] = kc >> 8, kc & 0xFF
            elif op == 0x15:
                self.enc[(c[1], c[2], c[3])] = c[4] << 8 | c[5]
            elif op == 0x0E:
                off, n = c[1] << 8 | c[2], c[3]
                r[4:4 + n] = self.macros[off:off + n]
            elif op == 0x0F:
                off, n = c[1] << 8 | c[2], c[3]
                self.macros[off:off + n] = bytes(c[4:4 + n])
            out.append(r[:32])
        return out

    def _keybuf(self):
        buf = []
        for l in range(self.layers):
            for row in range(vl.ROWS):
                for col in range(vl.COLS):
                    kc = self.keys.get((l, row, col), 0)
                    buf += [kc >> 8, kc & 0xFF]
        return buf


def defaults(over=None):
    keys = {(l, r, c): 0x68 + r * 5 + c for l in range(2) for r in range(4) for c in range(5)}
    enc = {(l, i, cw): 0x80 + i * 2 + cw for l in range(2) for i in range(3) for cw in (0, 1)}
    keys.update(over or {})
    return keys, enc


class ParseTest(unittest.TestCase):
    def test_parse_replies(self):
        replies = vl.parse_replies(REAL_OUTPUT, [[0x11], [0x0D]])
        self.assertEqual(replies[0][1], 8)
        self.assertEqual(replies[1][1] << 8 | replies[1][2], 0x237)

    def test_parse_rejects_misaligned(self):
        with self.assertRaises(vl.Fail):
            vl.parse_replies(REAL_OUTPUT, [[0x11], [0x0D], [0x12]])   # a reply is missing
        with self.assertRaises(vl.Fail):
            vl.parse_replies(REAL_OUTPUT, [[0x11], [0x12]])           # wrong command echoed


class LayoutTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.files = vl.Files(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_slot_names(self):
        self.assertEqual(vl.key_name(0, 0), "key1")
        self.assertEqual(vl.key_name(3, 3), "key16")
        self.assertEqual(vl.key_name(2, 4), "knob-big")
        self.assertEqual(vl.key_name(3, 4), "r3c4")

    def test_json_roundtrip(self):
        pad = FakePad("2026-11-23-01:00:00", *defaults())
        pad.macros[0:3] = b"hi\0"
        layout = vl.read_layout(pad)
        again = vl.from_json(vl.to_json(layout))
        self.assertEqual(again, layout)
        self.assertEqual(layout.slots["L1 key1"], 0x68)
        self.assertEqual(layout.slots["L2 enc2 cw"], 0x85)

    def test_first_flash_restores_nothing(self):
        keys, enc = defaults()
        pad = FakePad("A", keys, enc)
        pad.keys[(0, 0, 0)] = 0x04                  # an edit we can't prove is one
        vl.backup(pad, self.files)
        pad.flash("B", keys, enc)
        result = vl.restore(pad, self.files)
        self.assertEqual(result.restored, False)
        self.assertEqual(result.differences, ["L1 key1"])
        self.assertEqual(pad.keys[(0, 0, 0)], 0x68)
        self.assertEqual(vl.load(self.files.defaults).build, "B")

    def test_edit_survives_new_build(self):
        keys, enc = defaults()
        pad = FakePad("A", keys, enc)
        vl.restore(pad, self.files)                   # bootstrap: records A's defaults
        pad.keys[(1, 3, 3)] = 0x0173                  # user edit: L2 key16
        pad.enc[(0, 2, 1)] = 0x00A9                   # user edit: L1 enc2 cw
        pad.macros[0:3] = b"hi\0"
        vl.backup(pad, self.files)
        new_keys, new_enc = defaults({(0, 0, 1): 0x99, (1, 3, 3): 0x98})
        pad.flash("B", new_keys, new_enc)
        result = vl.restore(pad, self.files)
        self.assertTrue(result.restored)
        self.assertEqual(pad.keys[(1, 3, 3)], 0x0173)               # edit wins the conflict
        self.assertEqual(pad.enc[(0, 2, 1)], 0x00A9)
        self.assertEqual(pad.keys[(0, 0, 1)], 0x99)                 # untouched: new default
        self.assertEqual(bytes(pad.macros[0:3]), b"hi\0")
        self.assertEqual([c.slot for c in result.merge.conflicts], ["L2 key16"])

    def test_restore_twice_keeps_edits(self):
        keys, enc = defaults()
        pad = FakePad("A", keys, enc)
        vl.restore(pad, self.files)
        pad.keys[(0, 1, 1)] = 0x0004
        vl.backup(pad, self.files)
        pad.flash("B", keys, enc)
        vl.restore(pad, self.files)
        vl.restore(pad, self.files)                   # rerun must not undo it
        self.assertEqual(pad.keys[(0, 1, 1)], 0x0004)

    def test_set_and_apply(self):
        keys, enc = defaults()
        pad = FakePad("A", keys, enc)
        vl.set_slot(pad, "L2 key16", 0x0173)
        self.assertEqual(pad.keys[(1, 3, 3)], 0x0173)
        vl.backup(pad, self.files)
        pad.run([[0x06]])
        vl.apply(pad, self.files, ["L2 key16"])
        self.assertEqual(pad.keys[(1, 3, 3)], 0x0173)
        with self.assertRaises(vl.Fail):
            vl.set_slot(pad, "L2 key17", 1)


if __name__ == "__main__":
    unittest.main()
