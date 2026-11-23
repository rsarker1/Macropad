"""Merge rules for keeping VIA edits across flashes. Pure functions, no I/O.

A layout is a dict of slot name -> keycode (one key, or one knob direction).
An edit is a slot where the pad's layout differs from the defaults of the
build it was running. After a flash, edits go back on top of the new build's
defaults; untouched slots take the new defaults, so new features arrive.
See docs/superpowers/specs/2026-11-23-via-layout-backup-design.md.
"""

from dataclasses import dataclass, field

Slots = dict[str, int]


@dataclass
class Conflict:
    """The new build changed the default of a slot the user had edited."""
    slot: str
    kept: int          # the user's edit, which wins
    new_default: int   # what the new build wanted there


@dataclass
class MergeResult:
    merged: Slots
    edits: Slots
    conflicts: list[Conflict] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)  # edits with no slot in the new build


def edits(old_defaults: Slots, backup: Slots) -> Slots:
    return {s: v for s, v in backup.items() if old_defaults.get(s) != v}


def merge(old_defaults: Slots, backup: Slots, new_defaults: Slots) -> MergeResult:
    mine = edits(old_defaults, backup)
    result = MergeResult(merged=dict(new_defaults), edits=mine)
    for slot in sorted(mine):
        if slot not in new_defaults:
            result.dropped.append(slot)
            continue
        result.merged[slot] = mine[slot]
        old = old_defaults.get(slot)
        if old is not None and new_defaults[slot] != old and new_defaults[slot] != mine[slot]:
            result.conflicts.append(Conflict(slot, mine[slot], new_defaults[slot]))
    return result


def differences(a: Slots, b: Slots) -> list[str]:
    return sorted(s for s in a.keys() & b.keys() if a[s] != b[s])


def merge_macros(backup: bytes, size: int) -> bytes | None:
    """The macro buffer to write, or None when the backup has no macros.

    Macro defaults are always empty, so any macro in the backup is an edit.
    """
    used = backup.rstrip(b"\0")
    if not used:
        return None
    if len(used) >= size:  # keep room for the final terminator
        raise ValueError(f"macros need {len(used) + 1} bytes, the new build has {size}")
    return backup[:size].ljust(size, b"\0")
