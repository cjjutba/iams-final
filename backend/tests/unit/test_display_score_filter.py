"""Unit tests for the display-time SCRFD score floor.

The filter lives in
:py:meth:`app.services.realtime_tracker.RealtimeTracker._apply_display_score_filter`
and is applied at the very end of ``process()`` to suppress un-recognised
active tracks whose latest SCRFD detection score is below
``settings.MIN_DISPLAY_DET_SCORE``. The targeted failure mode is SCRFD
hallucinating a face on non-face objects (water gallons, ceiling fans,
wall sockets) — those typically score 0.30-0.45 and would otherwise
linger as static "Unknown" boxes in the admin overlay.

Coverage:
  * Active + un-recognised + score below floor → dropped.
  * Active + un-recognised + score at/above floor → kept.
  * Active + recognised, low score → kept (identity binding overrides).
  * Coasting (is_active=False), any score → kept (coasting path already
    only emits recognised tracks; no extra protection needed here).
  * Mutex-demoted track (user_id=None, recognition_state="warming_up")
    with score above floor → kept (filter does not double-punish it).
  * Floor disabled (0.0) → no-op even on garbage data.
  * Identity cache miss → treated as zero score → dropped if active+unknown.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.realtime_tracker import (
    RealtimeTracker,
    TrackIdentity,
    TrackResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tracker():
    """Tracker with all heavy deps mocked.

    The filter only touches ``_identity_cache`` and ``settings``, so we
    don't need a real InsightFace / FAISS / liveness backend.
    """
    return RealtimeTracker(
        insightface_model=MagicMock(),
        faiss_manager=MagicMock(),
        enrolled_user_ids={"user-A"},
        name_map={"user-A": "Alice"},
        schedule_id="sched-test",
        camera_id="cam-test",
        liveness_model=None,
    )


def _result(
    *,
    track_id: int,
    is_active: bool = True,
    recognition_state: str = "warming_up",
    user_id: str | None = None,
) -> TrackResult:
    return TrackResult(
        track_id=track_id,
        bbox=[0.1, 0.1, 0.2, 0.2],
        velocity=[0.0, 0.0, 0.0, 0.0],
        user_id=user_id,
        name="Alice" if user_id else None,
        confidence=0.7 if user_id else 0.0,
        status="recognized" if user_id else "pending",
        is_active=is_active,
        recognition_state=recognition_state,
    )


def _seed(
    tracker: RealtimeTracker,
    track_id: int,
    *,
    last_det_score: float,
    user_id: str | None = None,
    recognition_status: str = "pending",
) -> TrackIdentity:
    ident = TrackIdentity(
        track_id=track_id,
        user_id=user_id,
        recognition_status=recognition_status,
        last_det_score=last_det_score,
    )
    tracker._identity_cache[track_id] = ident
    return ident


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDisplayScoreFilter:
    def test_drops_unknown_active_track_below_floor(self, tracker):
        """The water-gallon scenario: SCRFD fired on a non-face at 0.35."""
        _seed(tracker, 1, last_det_score=0.35)
        results = [_result(track_id=1)]

        with patch("app.services.realtime_tracker.settings") as mock:
            mock.MIN_DISPLAY_DET_SCORE = 0.45
            out = tracker._apply_display_score_filter(results)

        assert out == []

    def test_keeps_unknown_active_track_at_or_above_floor(self, tracker):
        """A real face whose SCRFD score is healthy (e.g. 0.55) stays."""
        _seed(tracker, 1, last_det_score=0.55)
        results = [_result(track_id=1)]

        with patch("app.services.realtime_tracker.settings") as mock:
            mock.MIN_DISPLAY_DET_SCORE = 0.45
            out = tracker._apply_display_score_filter(results)

        assert len(out) == 1
        assert out[0].track_id == 1

    def test_keeps_unknown_active_track_exactly_at_floor(self, tracker):
        """Boundary: score == floor passes (>= comparison)."""
        _seed(tracker, 1, last_det_score=0.45)
        results = [_result(track_id=1)]

        with patch("app.services.realtime_tracker.settings") as mock:
            mock.MIN_DISPLAY_DET_SCORE = 0.45
            out = tracker._apply_display_score_filter(results)

        assert len(out) == 1

    def test_keeps_recognised_track_even_with_low_score(self, tracker):
        """Identity binding overrides per-frame SCRFD noise."""
        _seed(
            tracker,
            1,
            last_det_score=0.20,  # Far below floor — but irrelevant
            user_id="user-A",
            recognition_status="recognized",
        )
        results = [
            _result(
                track_id=1,
                user_id="user-A",
                recognition_state="recognized",
            )
        ]

        with patch("app.services.realtime_tracker.settings") as mock:
            mock.MIN_DISPLAY_DET_SCORE = 0.45
            out = tracker._apply_display_score_filter(results)

        assert len(out) == 1
        assert out[0].user_id == "user-A"

    def test_keeps_coasting_track_regardless_of_score(self, tracker):
        """is_active=False means already passed earlier emit gates."""
        _seed(tracker, 1, last_det_score=0.10)  # Stale score
        results = [_result(track_id=1, is_active=False)]

        with patch("app.services.realtime_tracker.settings") as mock:
            mock.MIN_DISPLAY_DET_SCORE = 0.45
            out = tracker._apply_display_score_filter(results)

        assert len(out) == 1

    def test_keeps_mutex_demoted_track_above_floor(self, tracker):
        """A mutex-demoted track has user_id=None + recognition_state=warming_up
        but its score is fine. Filter must not over-punish it."""
        _seed(tracker, 1, last_det_score=0.65)
        results = [
            _result(
                track_id=1,
                user_id=None,
                recognition_state="warming_up",
            )
        ]

        with patch("app.services.realtime_tracker.settings") as mock:
            mock.MIN_DISPLAY_DET_SCORE = 0.45
            out = tracker._apply_display_score_filter(results)

        assert len(out) == 1

    def test_drops_mutex_demoted_track_below_floor(self, tracker):
        """A mutex-demoted track that ALSO has a low SCRFD score is dropped
        (this is the "non-face object that briefly matched a real student"
        edge case — both the score and the user_id are now disqualifying)."""
        _seed(tracker, 1, last_det_score=0.30)
        results = [
            _result(
                track_id=1,
                user_id=None,
                recognition_state="warming_up",
            )
        ]

        with patch("app.services.realtime_tracker.settings") as mock:
            mock.MIN_DISPLAY_DET_SCORE = 0.45
            out = tracker._apply_display_score_filter(results)

        assert out == []

    def test_disabled_floor_is_noop(self, tracker):
        """MIN_DISPLAY_DET_SCORE=0 reverts to legacy behaviour."""
        _seed(tracker, 1, last_det_score=0.05)  # Garbage score
        _seed(tracker, 2, last_det_score=0.0)  # Zero score
        results = [_result(track_id=1), _result(track_id=2)]

        with patch("app.services.realtime_tracker.settings") as mock:
            mock.MIN_DISPLAY_DET_SCORE = 0.0
            out = tracker._apply_display_score_filter(results)

        assert len(out) == 2

    def test_missing_identity_cache_entry_drops_active_unknown(self, tracker):
        """If _identity_cache has no entry for the track (race / bug),
        the score is treated as 0 and the active+unknown track is dropped.
        This is the fail-safe direction."""
        # Note: no _seed() call — cache is empty for track 99.
        results = [_result(track_id=99)]

        with patch("app.services.realtime_tracker.settings") as mock:
            mock.MIN_DISPLAY_DET_SCORE = 0.45
            out = tracker._apply_display_score_filter(results)

        assert out == []

    def test_missing_identity_cache_entry_keeps_recognised(self, tracker):
        """If a recognised track is missing from cache (genuinely unusual
        but possible if reset() raced with broadcast), the recognition
        state still wins — keep painting the box."""
        results = [
            _result(
                track_id=99,
                user_id="user-A",
                recognition_state="recognized",
            )
        ]

        with patch("app.services.realtime_tracker.settings") as mock:
            mock.MIN_DISPLAY_DET_SCORE = 0.45
            out = tracker._apply_display_score_filter(results)

        assert len(out) == 1

    def test_mixed_batch_partial_filter(self, tracker):
        """Realistic scene: 1 real recognised face, 1 healthy unknown face,
        1 gallon false-positive. Only the gallon should be dropped."""
        _seed(
            tracker, 1,
            last_det_score=0.85,
            user_id="user-A",
            recognition_status="recognized",
        )
        _seed(tracker, 2, last_det_score=0.62)  # Real face, FAISS not yet committed
        _seed(tracker, 3, last_det_score=0.36)  # Water gallon

        results = [
            _result(track_id=1, user_id="user-A", recognition_state="recognized"),
            _result(track_id=2),
            _result(track_id=3),
        ]

        with patch("app.services.realtime_tracker.settings") as mock:
            mock.MIN_DISPLAY_DET_SCORE = 0.45
            out = tracker._apply_display_score_filter(results)

        kept_ids = {r.track_id for r in out}
        assert kept_ids == {1, 2}
