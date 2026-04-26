"""
Helpers for parsing and building CCTV-domain ``face_embeddings.angle_label``
values.

History:
  - Phase 1 (pre-2026-04-26): a single global label namespace ``cctv_<idx>``.
    Captured by both the manual ``scripts.cctv_enroll`` path and the
    background ``AutoCctvEnroller``. The auto-enroller's lifetime cap was
    therefore *global* per user — once five captures landed, no further
    captures fired even if the same user appeared in a different room
    where embeddings were missing.
  - Phase 2 (2026-04-26 onward): labels include the room key
    (``cctv_<room>_<idx>``), so auto-enrol can buffer captures per
    (user, room) pair. Existing ``cctv_<idx>`` rows continue to live in
    the FAISS index and the DB; they are treated as room-agnostic
    "legacy" captures by the parser. This module is the single source
    of truth for that mapping so consumers can't drift.

Examples::

    >>> parse_cctv_label("cctv_0")
    (None, 0)
    >>> parse_cctv_label("cctv_eb226_3")
    ('eb226', 3)
    >>> build_cctv_label("EB227", 4)
    'cctv_eb227_4'
    >>> build_cctv_label(None, 4)
    'cctv_4'

The parser is permissive: any ``cctv_<idx>`` shape is legacy, any
``cctv_<room>_<idx>`` shape with a non-numeric room slug is room-scoped.
A pathological ``cctv_5_0`` would be parsed as ``room='5', idx=0`` —
not a real risk since room keys are always alphabetic prefixes
(``eb226``, ``eb227``).
"""

from __future__ import annotations

import re

_LEGACY = re.compile(r"^cctv_(\d+)$")
_MODERN = re.compile(r"^cctv_([A-Za-z0-9-]+(?:_[A-Za-z0-9-]+)*)_(\d+)$")


def parse_cctv_label(label: str | None) -> tuple[str | None, int | None]:
    """Parse a CCTV face_embedding angle_label.

    Returns ``(room_key, idx)``. ``room_key`` is ``None`` for the
    legacy single-namespace ``cctv_<idx>`` form; it is the lower-cased
    room identifier for the modern ``cctv_<room>_<idx>`` form. ``idx``
    is ``None`` when the label is not a CCTV label at all (e.g. a
    phone angle like ``front``).
    """
    if not label:
        return None, None
    m = _LEGACY.match(label)
    if m:
        return None, int(m.group(1))
    m = _MODERN.match(label)
    if m:
        return m.group(1).lower(), int(m.group(2))
    return None, None


def is_cctv_label(label: str | None) -> bool:
    """True iff this is any CCTV label (legacy or modern)."""
    if not label:
        return False
    _, idx = parse_cctv_label(label)
    return idx is not None


def build_cctv_label(room_key: str | None, idx: int) -> str:
    """Build a CCTV angle_label.

    ``room_key=None`` produces the legacy ``cctv_<idx>`` form, kept as
    an escape hatch for callers without room context (e.g. unit tests).
    Production callers should always pass the normalised room key.
    """
    if room_key:
        return f"cctv_{normalize_room_key(room_key)}_{idx}"
    return f"cctv_{idx}"


def normalize_room_key(room: str | None) -> str:
    """Canonicalise a room identifier for use inside a label.

    Lowercases and strips whitespace. Hyphens / underscores are
    preserved; whitespace is dropped (``"EB 226"`` → ``"eb226"``) so
    accidental human-friendly spacing doesn't create a new namespace.
    """
    if not room:
        return ""
    return room.strip().lower().replace(" ", "")
