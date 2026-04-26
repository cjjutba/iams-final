"""
Back-row (cropped) stream registry — distant-face plan 2026-04-26 Phase 2.

A back-row stream is a software-cropped re-encode of a primary CCTV stream
that publishes to mediamtx under a parallel path (``eb226-back`` alongside
``eb226``). Cropping the upper 60 % of the frame roughly doubles pixel
density on far faces — students at the back wall who arrive at SCRFD as
~25 px on the wide stream become ~50 px on the cropped one, well above
the buffalo_l detection floor.

This module:

  - Parses ``settings.BACKROW_CROP_STREAMS`` (a comma-separated list of
    ``primary_key=>backrow_path`` entries) into a structured map.
  - Boots a secondary ``FrameGrabber`` per primary stream when present
    in the config.
  - Provides ``lookup_backrow_grabber(room_stream_key)`` for the
    SessionPipeline's start() path so the parallel tracker can attach
    to the right RTSP source.

Boundaries:

  - The secondary grabbers live in their own ``app.state`` dict
    (``backrow_frame_grabbers``) keyed by the ``backrow_path`` (e.g.
    ``eb226-back``), NOT by room_id. Multiple rooms could conceivably
    share a back-row path in some weird future config; keying off the
    target path keeps the registry honest.
  - Detection results from a back-row tracker do NOT flow to the WS
    overlay. Coordinate spaces don't match the wide stream, and the
    admin live page only renders one video. The back-row tracker's
    output is plumbed straight into the shared ``TrackPresenceService``
    so identity dedup happens at user_id and presence accumulates from
    whichever camera saw the student first.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BackrowStream:
    """One mapping from a primary stream_key to its cropped sibling."""

    primary_stream_key: str
    backrow_path: str  # mediamtx path, NOT a full URL

    @property
    def rtsp_url(self) -> str:
        """Full RTSP URL the FrameGrabber binds to."""
        return f"{settings.MEDIAMTX_RTSP_URL.rstrip('/')}/{self.backrow_path}"


def parse_backrow_config(raw: str | None) -> list[BackrowStream]:
    """Parse ``settings.BACKROW_CROP_STREAMS`` into structured entries.

    Empty / None / whitespace input → empty list (Phase 2 disabled).
    Bad entries are logged and skipped so a single typo doesn't break
    the whole startup path.
    """
    if not raw:
        return []
    out: list[BackrowStream] = []
    seen_primary: set[str] = set()
    seen_backrow: set[str] = set()
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=>" not in entry:
            logger.warning(
                "BACKROW_CROP_STREAMS: skipping malformed entry %r "
                "(expected 'primary=>backrow_path')",
                entry,
            )
            continue
        primary, _, backrow = entry.partition("=>")
        primary = primary.strip()
        backrow = backrow.strip()
        if not primary or not backrow:
            logger.warning(
                "BACKROW_CROP_STREAMS: skipping empty primary or backrow in %r",
                entry,
            )
            continue
        if primary in seen_primary:
            logger.warning(
                "BACKROW_CROP_STREAMS: duplicate primary %r — first wins",
                primary,
            )
            continue
        if backrow in seen_backrow:
            logger.warning(
                "BACKROW_CROP_STREAMS: duplicate backrow path %r — first wins",
                backrow,
            )
            continue
        seen_primary.add(primary)
        seen_backrow.add(backrow)
        out.append(BackrowStream(primary_stream_key=primary, backrow_path=backrow))
    return out


def is_enabled() -> bool:
    """True when at least one back-row stream is configured."""
    return bool(parse_backrow_config(settings.BACKROW_CROP_STREAMS))
