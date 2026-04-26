"""
Unit tests for the per-track recognition diagnostics surfaced via the
Track Detail panel (added 2026-04-26).

Targets the pure-logic helpers on ``RealtimeTracker`` —
``_classify_commit_reason``, ``_effective_threshold_for``,
``_record_decision_diagnostic``, and ``_record_no_search_diagnostic``.
The full integration path (``_recognize_batch`` → ``_commit_decision``
→ TrackResult build → WS broadcast) needs SCRFD/ArcFace + FAISS state
to exercise meaningfully and is covered by the on-prem smoke runs.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

# The tracker module imports cv2 + supervision at module load time which
# is fine in the venv but means we need the backend on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.realtime_tracker import (  # noqa: E402
    RealtimeTracker,
    TrackIdentity,
    _BatchDecision,
)


# ─── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def tracker():
    """A RealtimeTracker with no real ML — all backend deps mocked.

    Only the pure-logic methods are exercised, so we don't need SCRFD,
    FAISS, or ByteTrack to actually do anything.
    """
    insight = MagicMock()
    insight.app = None  # so process() short-circuits if accidentally called
    faiss = MagicMock()
    return RealtimeTracker(
        insightface_model=insight,
        faiss_manager=faiss,
        enrolled_user_ids={"user-a", "user-b"},
        name_map={"user-a": "Alice Atom", "user-b": "Bob Boson"},
        schedule_id="sch-test",
        camera_id="eb226",
        phone_only_user_ids={"user-b"},  # Bob is phone-only
    )


def _make_identity(track_id: int = 1, **kwargs) -> TrackIdentity:
    """Construct a minimal TrackIdentity with sensible defaults."""
    defaults = dict(
        track_id=track_id,
        first_seen=0.0,
        last_seen=1.0,
    )
    defaults.update(kwargs)
    return TrackIdentity(**defaults)


def _make_decision(
    identity: TrackIdentity,
    *,
    user_id: str | None = None,
    confidence: float = 0.0,
    is_ambiguous: bool = False,
    top1_user_id: str | None = None,
    top1_score: float = 0.0,
    top2_user_id: str | None = None,
    top2_score: float = 0.0,
    swap_blocked: bool = False,
    mutex_demoted: bool = False,
    resolved_name: str | None = None,
    is_revalidation: bool = False,
) -> _BatchDecision:
    """Construct a _BatchDecision with diagnostic fields filled in."""
    return _BatchDecision(
        identity=identity,
        search_embedding=np.zeros(512, dtype=np.float32),
        live_crop=np.zeros((10, 10, 3), dtype=np.uint8),
        det_score=0.9,
        bbox_px=[0, 0, 10, 10],
        user_id=user_id,
        confidence=confidence,
        is_ambiguous=is_ambiguous,
        resolved_name=resolved_name,
        top1_user_id=top1_user_id,
        top1_score=top1_score,
        top2_user_id=top2_user_id,
        top2_score=top2_score,
        swap_blocked=swap_blocked,
        mutex_demoted=mutex_demoted,
        is_revalidation=is_revalidation,
    )


# ─── _effective_threshold_for ─────────────────────────────────────────


class TestEffectiveThreshold:
    def test_standard_user(self, tracker):
        """Non-phone-only users get the bare RECOGNITION_THRESHOLD."""
        from app.config import settings

        result = tracker._effective_threshold_for("user-a")
        assert result == settings.RECOGNITION_THRESHOLD

    def test_phone_only_user_gets_bonus(self, tracker):
        """Phone-only users get the +PHONE_ONLY_THRESHOLD_BONUS bump."""
        from app.config import settings

        expected = (
            settings.RECOGNITION_THRESHOLD
            + settings.RECOGNITION_PHONE_ONLY_THRESHOLD_BONUS
        )
        result = tracker._effective_threshold_for("user-b")
        assert result == pytest.approx(expected)

    def test_none_user(self, tracker):
        """None user_id falls through to the standard threshold."""
        from app.config import settings

        assert tracker._effective_threshold_for(None) == settings.RECOGNITION_THRESHOLD


# ─── _classify_commit_reason ──────────────────────────────────────────


class TestClassifyCommitReason:
    def test_matched_happy_path(self, tracker):
        identity = _make_identity()
        d = _make_decision(
            identity,
            user_id="user-a",
            confidence=0.75,
            top1_user_id="user-a",
            top1_score=0.75,
            resolved_name="Alice Atom",
        )
        assert tracker._classify_commit_reason(d, identity, False) == "matched"

    def test_below_threshold(self, tracker):
        from app.config import settings

        identity = _make_identity()
        weak_score = settings.RECOGNITION_THRESHOLD - 0.1
        d = _make_decision(
            identity,
            top1_user_id="user-a",
            top1_score=weak_score,
            is_ambiguous=True,
        )
        assert (
            tracker._classify_commit_reason(d, identity, True) == "below_threshold"
        )

    def test_below_phone_only_threshold(self, tracker):
        """Phone-only user (Bob) clears standard but misses the bonus gate."""
        from app.config import settings

        identity = _make_identity()
        # Score that clears RECOGNITION_THRESHOLD but not the phone-only bump.
        score = settings.RECOGNITION_THRESHOLD + 0.01
        # (Sanity check the test setup makes sense — score must lie inside
        # the phone-only band.)
        assert score < (
            settings.RECOGNITION_THRESHOLD
            + settings.RECOGNITION_PHONE_ONLY_THRESHOLD_BONUS
        )
        d = _make_decision(
            identity,
            user_id=None,  # phone-only gate clears user_id
            top1_user_id="user-b",  # Bob is phone-only in the fixture
            top1_score=score,
            is_ambiguous=True,
        )
        assert (
            tracker._classify_commit_reason(d, identity, True)
            == "below_phone_only_threshold"
        )

    def test_no_faiss_hit(self, tracker):
        identity = _make_identity()
        d = _make_decision(identity, top1_user_id=None, top1_score=0.0)
        assert tracker._classify_commit_reason(d, identity, True) == "no_faiss_hit"

    def test_swap_blocked(self, tracker):
        identity = _make_identity()
        d = _make_decision(
            identity,
            user_id="user-a",  # incumbent retained by swap-gate
            confidence=0.6,
            top1_user_id="user-c",
            top1_score=0.7,
            swap_blocked=True,
        )
        # is_ambiguous=False because the incumbent committed; swap_blocked
        # flag is what we're testing
        assert tracker._classify_commit_reason(d, identity, False) == "matched"
        # And when ambiguous (swap held but new candidate didn't win):
        d2 = _make_decision(
            identity,
            user_id=None,
            top1_user_id="user-c",
            top1_score=0.7,
            swap_blocked=True,
            is_ambiguous=True,
        )
        assert tracker._classify_commit_reason(d2, identity, True) == "swap_blocked"

    def test_mutex_demoted_takes_precedence(self, tracker):
        """Mutex demotion is the more interesting reason than swap_blocked
        when both are flagged on the same decision."""
        identity = _make_identity()
        d = _make_decision(
            identity,
            user_id=None,
            top1_user_id="user-a",
            top1_score=0.7,
            swap_blocked=True,
            mutex_demoted=True,
            is_ambiguous=True,
        )
        assert (
            tracker._classify_commit_reason(d, identity, True) == "mutex_demoted"
        )

    def test_orphaned_user_id(self, tracker):
        """FAISS top-1 names a user not in the name_map → orphaned."""
        from app.config import settings

        identity = _make_identity()
        d = _make_decision(
            identity,
            user_id=None,  # _gather_decisions cleared it on resolve_name miss
            top1_user_id="ghost-user",  # not in the fixture's name_map
            top1_score=settings.RECOGNITION_THRESHOLD + 0.1,
            is_ambiguous=True,
        )
        assert tracker._classify_commit_reason(d, identity, True) == "orphaned_user_id"


# ─── _record_decision_diagnostic ──────────────────────────────────────


class TestRecordDecisionDiagnostic:
    def test_writes_all_fields(self, tracker):
        identity = _make_identity()
        d = _make_decision(
            identity,
            user_id="user-a",
            confidence=0.75,
            top1_user_id="user-a",
            top1_score=0.75,
            top2_user_id="user-b",
            top2_score=0.40,
            swap_blocked=False,
            mutex_demoted=False,
        )
        tracker._record_decision_diagnostic(
            identity, d, "matched", 0.5, now=10.0
        )
        assert identity.last_top1_user_id == "user-a"
        assert identity.last_top1_score == pytest.approx(0.75)
        assert identity.last_top1_name == "Alice Atom"
        assert identity.last_top2_user_id == "user-b"
        assert identity.last_top2_score == pytest.approx(0.40)
        assert identity.last_top2_name == "Bob Boson"
        assert identity.last_decision_reason == "matched"
        assert identity.last_decision_at == 10.0
        assert identity.last_effective_threshold == pytest.approx(0.5)
        assert identity.last_decision_searched is True
        assert identity.last_swap_blocked is False
        assert identity.last_mutex_demoted is False

    def test_unresolved_top1_name(self, tracker):
        """Top-1 user_id with no name_map entry → last_top1_name is None."""
        identity = _make_identity()
        d = _make_decision(
            identity,
            top1_user_id="ghost-user",
            top1_score=0.55,
        )
        tracker._record_decision_diagnostic(
            identity, d, "orphaned_user_id", 0.5, now=5.0
        )
        assert identity.last_top1_user_id == "ghost-user"
        assert identity.last_top1_name is None

    def test_swap_blocked_flag_propagates(self, tracker):
        identity = _make_identity()
        d = _make_decision(
            identity,
            user_id="user-a",
            top1_user_id="user-c",
            top1_score=0.65,
            swap_blocked=True,
        )
        tracker._record_decision_diagnostic(
            identity, d, "matched", 0.5, now=2.0
        )
        assert identity.last_swap_blocked is True

    def test_does_not_corrupt_recognition_state(self, tracker):
        """Writing diagnostics MUST NOT touch ``recognition_status`` or
        any field that influences matching decisions."""
        identity = _make_identity(
            recognition_status="recognized",
            user_id="user-a",
            confidence=0.75,
            name="Alice Atom",
            unknown_attempts=0,
        )
        d = _make_decision(
            identity,
            user_id="user-a",
            confidence=0.65,
            top1_user_id="user-a",
            top1_score=0.65,
        )
        before = (
            identity.recognition_status,
            identity.user_id,
            identity.confidence,
            identity.name,
            identity.unknown_attempts,
        )
        tracker._record_decision_diagnostic(
            identity, d, "matched", 0.5, now=99.0
        )
        after = (
            identity.recognition_status,
            identity.user_id,
            identity.confidence,
            identity.name,
            identity.unknown_attempts,
        )
        assert before == after


class TestRecordNoSearchDiagnostic:
    def test_marks_not_searched(self, tracker):
        identity = _make_identity(
            last_top1_user_id="user-a",
            last_top1_score=0.75,
            last_decision_reason="matched",
            last_decision_searched=True,
        )
        tracker._record_no_search_diagnostic(
            identity, reason="reverify_not_due", now=20.0
        )
        # Reason updates but the previous top-1/2 are preserved (the UI
        # keeps showing the last actual FAISS result).
        assert identity.last_decision_reason == "reverify_not_due"
        assert identity.last_decision_at == 20.0
        assert identity.last_decision_searched is False
        assert identity.last_top1_user_id == "user-a"
        assert identity.last_top1_score == pytest.approx(0.75)


# ─── _diagnostic_fields (to TrackResult kwargs) ───────────────────────


class TestDiagnosticFieldsKwargs:
    def test_none_returns_empty_dict(self, tracker):
        assert tracker._diagnostic_fields(None) == {}

    def test_full_identity_emits_all_fields(self, tracker):
        identity = _make_identity(
            last_top1_user_id="user-a",
            last_top1_score=0.71,
            last_top1_name="Alice Atom",
            last_top2_user_id="user-b",
            last_top2_score=0.33,
            last_top2_name="Bob Boson",
            last_decision_reason="matched",
            last_effective_threshold=0.5,
            last_decision_searched=True,
            last_swap_blocked=False,
            last_mutex_demoted=False,
            best_score_seen=0.81,
            unknown_attempts=0,
            frames_seen=42,
        )
        out = tracker._diagnostic_fields(identity)
        assert out["top1_user_id"] == "user-a"
        assert out["top1_score"] == pytest.approx(0.71)
        assert out["top1_name"] == "Alice Atom"
        assert out["top2_user_id"] == "user-b"
        assert out["top2_score"] == pytest.approx(0.33)
        assert out["top2_name"] == "Bob Boson"
        assert out["decision_reason"] == "matched"
        assert out["effective_threshold"] == pytest.approx(0.5)
        assert out["decision_searched"] is True
        assert out["swap_blocked"] is False
        assert out["mutex_demoted"] is False
        assert out["best_score_seen"] == pytest.approx(0.81)
        assert out["unknown_attempts"] == 0
        assert out["frames_seen"] == 42

    def test_kwargs_match_TrackResult_signature(self, tracker):
        """Validates that the kwargs returned by _diagnostic_fields are
        actually accepted by TrackResult's constructor — guards against
        future field-name drift between the two."""
        from app.services.realtime_tracker import TrackResult

        identity = _make_identity(
            last_top1_user_id="user-a",
            last_top1_score=0.71,
            last_top1_name="Alice Atom",
        )
        kwargs = tracker._diagnostic_fields(identity)
        # Should not raise.
        result = TrackResult(
            track_id=1,
            bbox=[0.0, 0.0, 0.5, 0.5],
            velocity=[0.0, 0.0, 0.0, 0.0],
            user_id=None,
            name=None,
            confidence=0.0,
            status="pending",
            is_active=False,
            **kwargs,
        )
        assert result.top1_user_id == "user-a"
        assert result.top1_score == pytest.approx(0.71)
