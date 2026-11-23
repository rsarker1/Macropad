import unittest

from via_merge import Conflict, differences, edits, merge, merge_macros

OLD = {"L1 key1": 0x0268, "L1 key2": 0x00AC, "L1 enc2 cw": 0x00A9}


class MergeTest(unittest.TestCase):
    def test_no_edits(self):
        new = dict(OLD, **{"L1 key2": 0x00AD})
        r = merge(OLD, dict(OLD), new)
        self.assertEqual(r.merged, new)
        self.assertEqual(r.edits, {})
        self.assertEqual(r.conflicts, [])

    def test_edit_kept(self):
        backup = dict(OLD, **{"L1 key1": 0x0004})
        r = merge(OLD, backup, dict(OLD))
        self.assertEqual(r.merged["L1 key1"], 0x0004)
        self.assertEqual(r.edits, {"L1 key1": 0x0004})
        self.assertEqual(r.conflicts, [])

    def test_untouched_takes_new_default(self):
        backup = dict(OLD, **{"L1 key1": 0x0004})
        new = dict(OLD, **{"L1 enc2 cw": 0x0080})
        r = merge(OLD, backup, new)
        self.assertEqual(r.merged["L1 enc2 cw"], 0x0080)
        self.assertEqual(r.merged["L1 key1"], 0x0004)

    def test_conflict_edit_wins(self):
        backup = dict(OLD, **{"L1 key2": 0x0004})
        new = dict(OLD, **{"L1 key2": 0x0173})
        r = merge(OLD, backup, new)
        self.assertEqual(r.merged["L1 key2"], 0x0004)
        self.assertEqual(r.conflicts, [Conflict("L1 key2", 0x0004, 0x0173)])

    def test_dropped_slot(self):
        old = dict(OLD, **{"L9 key1": 0x0068})
        backup = dict(old, **{"L9 key1": 0x0004})
        r = merge(old, backup, dict(OLD))
        self.assertEqual(r.dropped, ["L9 key1"])
        self.assertNotIn("L9 key1", r.merged)

    def test_differences(self):
        self.assertEqual(differences(OLD, dict(OLD, **{"L1 key2": 1})), ["L1 key2"])


class MacroTest(unittest.TestCase):
    def test_macros_empty_is_none(self):
        self.assertIsNone(merge_macros(bytes(10), 20))

    def test_macros_padded(self):
        self.assertEqual(merge_macros(b"ab\0", 5), b"ab\0\0\0")

    def test_macros_too_big(self):
        with self.assertRaises(ValueError):
            merge_macros(b"abcdef", 4)

    def test_macros_trailing_zeros_fit(self):
        self.assertEqual(merge_macros(b"ab\0\0\0\0", 3), b"ab\0")


if __name__ == "__main__":
    unittest.main()
