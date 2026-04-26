"""Unit tests for the ByteTrack ID-switch identity hand-off pass.

The hand-off helper lives in
:py:meth:`app.services.realtime_tracker.RealtimeTracker._perform_identity_handoff`
— see that module's docstring for the full architecture story. The tests
here exercise the helper in isolation against a hand-built
``_identity_cache`` so we don't have to drag in InsightFace, FAISS, or
the ByteTrack stack.

Coverage:
  * Single donor + single recipient within proximity → transfer commits,
    donor evicted, recipient inherits identity fields.
  * Donor too old → no transfer (display-coast cap protects us).
  * Distance beyond the threshold → no transfer.
  * Two recipients near one donor → ambiguous, no transfer.
  * Two donors near one recipient → ambiguous, no transfer.
  * Recipient that has been alive too many frames → no transfer (avoid
    stealing from an established new track that's already FAISS-pending).
  * Recipient that already has a recognised identity → not a donor candidate.
  * Disabled flag → no transfer regardless of proximity.

The helper mutates ``_identity_cache`` in place and returns
``{recipient_track_id: donor_track_id}`` for every commit, which the
tests assert directly.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from app.config import settings
from app.services.realtime_tracker import RealtimeTracker, TrackIdentity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tracker():
    """A RealtimeTracker with all heavy dependencies mocked.

    The hand-off pass only touches ``_identity_cache``, ``_prev_bboxes``,
    and the static settings module, so mock InsightFace + FAISS + the
    optional liveness model. We do NOT call ``process()`` in these
    tests; ``_perform_identity_handoff`` is exercised directly.
    """
    insight = MagicMock()
    faiss = MagicMock()
    return RealtimeTracker(
        insightface_model=insight,
        faiss_manager=faiss,
        enrolled_user_ids={"user-A", "user-B"},
        name_map={"user-A": "Alice", "user-B": "Bob"},
        schedule_id="sched-test",
        camera_id="cam-test",
        liveness_model=None,
    )


def _make_identity(
    track_id: int,
    *,
    user_id: str | None,
    name: str | None,
    status: str,
    last_bbox: list[float] | None,
    frames_seen: int = 1,
    last_seen: float = 0.0,
    first_seen: float = 0.0,
    confidence: float = 0.7,
    embeddings: list[np.ndarray] | None = None,
) -> TrackIdentity:
    ident = TrackIdentity(
        track_id=track_id,
        user_id=user_id,
        name=name,
        confidence=confidence,
        first_seen=first_seen,
        last_seen=last_seen,
        last_verified=last_seen,
        recognition_status=status,
        frames_seen=frames_seen,
        last_bbox=list(last_bbox) if last_bbox is not None else None,
    )
    if embeddings:
        for emb in embeddings:
            ident.embedding_buffer.append(emb)
    return ident


# Helper: build a normalised bbox centred on (cx, cy) with half-edge 0.05.
def _bbox_at(cx: float, cy: float, half: float = 0.05) -> list[float]:
    return [cx - half, cy - half, cx + half, cy + half]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestIdentityHandoffHappyPath:
    def test_transfer_commits_for_single_donor_recipient_pair(self, tracker):
        """A lost recognised track + nearby newborn pending track → transfer."""
        now = 100.0
        donor = _make_identity(
            track_id=1,
            user_id="user-A",
            name="Alice",
            status="recognized",
            last_bbox=_bbox_at(0.50, 0.50),
            frames_seen=20,
            first_seen=80.0,
            last_seen=now - 0.3,  # Lost 0.3 s ago, well under MAX_AGE_S
            confidence=0.82,
            embeddings=[np.ones(512, dtype=np.float32)],
        )
        recipient = _make_identity(
            track_id=42,
            user_id=None,
            name=None,
            status="pending",
            last_bbox=_bbox_at(0.55, 0.50),  # 0.05 normalized away
            frames_seen=1,
            first_seen=now,
            last_seen=now,
        )
        tracker._identity_cache[1] = donor
        tracker._identity_cache[42] = recipient

        transfers = tracker._perform_identity_handoff({42}, now)

        assert transfers == {42: 1}
        assert 1 not in tracker._identity_cache, "donor must be evicted"
        merged = tracker._identity_cache[42]
        assert merged.user_id == "user-A"
        assert merged.name == "Alice"
        assert merged.recognition_status == "recognized"
        assert merged.confidence == pytest.approx(0.82)
        assert merged.last_verified == pytest.approx(now)
        assert merged.unknown_attempts == 0
        assert len(merged.embedding_buffer) == 1
        # first_seen must NOT inherit — recipient keeps its own first-seen
        # so wall-clock book-keeping (warming_up ceiling, etc.) restarts.
        assert merged.first_seen == pytest.approx(now)

    def test_transfer_carries_oscillation_and_hold_state(self, tracker):
        """Hold + oscillation history must follow the identity to the recipient."""
        now = 200.0
        donor = _make_identity(
            track_id=7,
            user_id="user-B",
            name="Bob",
            status="recognized",
            last_bbox=_bbox_at(0.30, 0.30),
            last_seen=now - 0.2,
            first_seen=now - 5.0,
        )
        donor.held_user_id = "user-B"
        donor.held_name = "Bob"
        donor.held_confidence = 0.74
        donor.held_at = now - 1.0
        donor.swap_history.append((now - 4.0, "user-X"))
        donor.oscillation_uncertain_until = now + 2.0
        donor.best_score_seen = 0.91

        recipient = _make_identity(
            track_id=99,
            user_id=None,
            name=None,
            status="pending",
            last_bbox=_bbox_at(0.32, 0.30),
            frames_seen=2,
            last_seen=now,
            first_seen=now,
        )
        tracker._identity_cache[7] = donor
        tracker._identity_cache[99] = recipient

        transfers = tracker._perform_identity_handoff({99}, now)

        assert transfers == {99: 7}
        merged = tracker._identity_cache[99]
        assert merged.held_user_id == "user-B"
        assert merged.held_at == pytest.approx(now - 1.0)
        assert list(merged.swap_history) == [(now - 4.0, "user-X")]
        assert merged.oscillation_uncertain_until == pytest.approx(now + 2.0)
        assert merged.best_score_seen == pytest.approx(0.91)


# ---------------------------------------------------------------------------
# Negative cases
# ---------------------------------------------------------------------------


class TestIdentityHandoffRejections:
    def test_donor_too_old_not_transferred(self, tracker):
        """A donor outside MAX_AGE_S is invisible to the hand-off pass."""
        now = 50.0
        donor = _make_identity(
            track_id=1,
            user_id="user-A",
            name="Alice",
            status="recognized",
            last_bbox=_bbox_at(0.5, 0.5),
            last_seen=now - (settings.IDENTITY_HANDOFF_MAX_AGE_S + 0.1),
        )
        recipient = _make_identity(
            track_id=2,
            user_id=None,
            name=None,
            status="pending",
            last_bbox=_bbox_at(0.5, 0.5),
            frames_seen=1,
            last_seen=now,
        )
        tracker._identity_cache[1] = donor
        tracker._identity_cache[2] = recipient

        transfers = tracker._perform_identity_handoff({2}, now)

        assert transfers == {}
        assert tracker._identity_cache[2].user_id is None
        # Donor stays in cache — TRACK_LOST_TIMEOUT controls eviction,
        # not the hand-off pass.
        assert 1 in tracker._identity_cache

    def test_distance_beyond_threshold_not_transferred(self, tracker):
        """Spatial gate: centre distance > MAX_DIST_NORMALIZED → no transfer."""
        now = 100.0
        donor = _make_identity(
            track_id=1,
            user_id="user-A",
            name="Alice",
            status="recognized",
            last_bbox=_bbox_at(0.10, 0.10),
            last_seen=now - 0.1,
        )
        # Recipient sits across the frame.
        recipient = _make_identity(
            track_id=2,
            user_id=None,
            name=None,
            status="pending",
            last_bbox=_bbox_at(0.90, 0.90),
            frames_seen=1,
            last_seen=now,
        )
        tracker._identity_cache[1] = donor
        tracker._identity_cache[2] = recipient

        transfers = tracker._perform_identity_handoff({2}, now)

        assert transfers == {}
        assert tracker._identity_cache[2].user_id is None

    def test_two_recipients_near_one_donor_is_ambiguous(self, tracker):
        """When two newborns sit near one lost track, refuse to transfer."""
        now = 100.0
        donor = _make_identity(
            track_id=1,
            user_id="user-A",
            name="Alice",
            status="recognized",
            last_bbox=_bbox_at(0.50, 0.50),
            last_seen=now - 0.1,
        )
        rec_a = _make_identity(
            track_id=10,
            user_id=None,
            name=None,
            status="pending",
            last_bbox=_bbox_at(0.52, 0.50),
            frames_seen=1,
            last_seen=now,
        )
        rec_b = _make_identity(
            track_id=11,
            user_id=None,
            name=None,
            status="pending",
            last_bbox=_bbox_at(0.48, 0.50),
            frames_seen=1,
            last_seen=now,
        )
        tracker._identity_cache[1] = donor
        tracker._identity_cache[10] = rec_a
        tracker._identity_cache[11] = rec_b

        transfers = tracker._perform_identity_handoff({10, 11}, now)

        assert transfers == {}
        # Donor must NOT have been evicted by an ambiguous attempt.
        assert 1 in tracker._identity_cache
        assert tracker._identity_cache[10].user_id is None
        assert tracker._identity_cache[11].user_id is None

    def test_two_donors_near_one_recipient_is_ambiguous(self, tracker):
        """Reciprocal: two lost tracks near one newborn → no transfer."""
        now = 100.0
        donor_a = _make_identity(
            track_id=1,
            user_id="user-A",
            name="Alice",
            status="recognized",
            last_bbox=_bbox_at(0.48, 0.50),
            last_seen=now - 0.1,
        )
        donor_b = _make_identity(
            track_id=2,
            user_id="user-B",
            name="Bob",
            status="recognized",
            last_bbox=_bbox_at(0.52, 0.50),
            last_seen=now - 0.1,
        )
        recipient = _make_identity(
            track_id=99,
            user_id=None,
            name=None,
            status="pending",
            last_bbox=_bbox_at(0.50, 0.50),
            frames_seen=1,
            last_seen=now,
        )
        tracker._identity_cache[1] = donor_a
        tracker._identity_cache[2] = donor_b
        tracker._identity_cache[99] = recipient

        transfers = tracker._perform_identity_handoff({99}, now)

        assert transfers == {}
        assert tracker._identity_cache[99].user_id is None

    def test_established_recipient_not_eligible(self, tracker):
        """Newborn that already has many frames must not steal identity.

        After ``IDENTITY_HANDOFF_MAX_FRAMES_SEEN`` the track has its own
        identity story (FAISS attempts, oscillation history, etc.) — letting
        a lost neighbour overwrite that would be the wrong call.
        """
        now = 100.0
        donor = _make_identity(
            track_id=1,
            user_id="user-A",
            name="Alice",
            status="recognized",
            last_bbox=_bbox_at(0.50, 0.50),
            last_seen=now - 0.1,
        )
        recipient = _make_identity(
            track_id=2,
            user_id=None,
            name=None,
            status="pending",
            last_bbox=_bbox_at(0.50, 0.50),
            frames_seen=settings.IDENTITY_HANDOFF_MAX_FRAMES_SEEN + 1,
            last_seen=now,
        )
        tracker._identity_cache[1] = donor
        tracker._identity_cache[2] = recipient

        transfers = tracker._perform_identity_handoff({2}, now)

        assert transfers == {}

    def test_recognised_recipient_not_eligible(self, tracker):
        """Recipient must be 'pending' — already-recognised tracks are skipped."""
        now = 100.0
        donor = _make_identity(
            track_id=1,
            user_id="user-A",
            name="Alice",
            status="recognized",
            last_bbox=_bbox_at(0.50, 0.50),
            last_seen=now - 0.1,
        )
        recipient = _make_identity(
            track_id=2,
            user_id="user-B",
            name="Bob",
            status="recognized",
            last_bbox=_bbox_at(0.50, 0.50),
            frames_seen=1,
            last_seen=now,
        )
        tracker._identity_cache[1] = donor
        tracker._identity_cache[2] = recipient

        transfers = tracker._perform_identity_handoff({2}, now)

        assert transfers == {}
        assert tracker._identity_cache[2].user_id == "user-B"

    def test_disabled_flag_short_circuits(self, tracker, monkeypatch):
        """``IDENTITY_HANDOFF_ENABLED=False`` must skip all work."""
        now = 100.0
        donor = _make_identity(
            track_id=1,
            user_id="user-A",
            name="Alice",
            status="recognized",
            last_bbox=_bbox_at(0.50, 0.50),
            last_seen=now - 0.1,
        )
        recipient = _make_identity(
            track_id=2,
            user_id=None,
            name=None,
            status="pending",
            last_bbox=_bbox_at(0.50, 0.50),
            frames_seen=1,
            last_seen=now,
        )
        tracker._identity_cache[1] = donor
        tracker._identity_cache[2] = recipient

        monkeypatch.setattr(settings, "IDENTITY_HANDOFF_ENABLED", False)
        transfers = tracker._perform_identity_handoff({2}, now)

        assert transfers == {}
        assert tracker._identity_cache[2].user_id is None
        assert 1 in tracker._identity_cache

    def test_donor_present_in_active_ids_skipped(self, tracker):
        """A donor that DID receive a detection this frame is not lost,
        so it must not be a hand-off donor."""
        now = 100.0
        donor = _make_identity(
            track_id=1,
            user_id="user-A",
            name="Alice",
            status="recognized",
            last_bbox=_bbox_at(0.50, 0.50),
            last_seen=now,
        )
        recipient = _make_identity(
            track_id=2,
            user_id=None,
            name=None,
            status="pending",
            last_bbox=_bbox_at(0.50, 0.50),
            frames_seen=1,
            last_seen=now,
        )
        tracker._identity_cache[1] = donor
        tracker._identity_cache[2] = recipient

        # Donor IS active this frame.
        transfers = tracker._perform_identity_handoff({1, 2}, now)

        assert transfers == {}
        assert 1 in tracker._identity_cache
        assert tracker._identity_cache[2].user_id is None
