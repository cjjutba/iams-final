"""
Track Fusion Service

Fuses fast edge detections (15 FPS) with slow identity recognition (2 FPS)
into smooth Kalman-predicted tracks at 30 FPS output. Uses a constant-velocity
Kalman filter to predict bounding box positions between measurements.

Architecture:
- Edge detections arrive via update_from_edge() at ~15 FPS
- Identity results arrive via update_identity() at ~2 FPS
- predict() advances all tracks forward for smooth interpolation
- get_tracks() returns current fused state for WebSocket broadcast
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import numpy as np

from app.config import logger

# ── Kalman filter constants ──────────────────────────────────────────────────

# Measurement matrix H: observes [cx, cy, w, h] from 8-dim state
H = np.eye(4, 8, dtype=np.float64)

# Base process noise (scaled by dt)
Q_BASE = np.diag([0.5, 0.5, 0.25, 0.25, 3.0, 3.0, 0.5, 0.5])

# Measurement noise
R = np.diag([6.0, 6.0, 6.0, 6.0])


def _make_F(dt: float) -> np.ndarray:
    """Build state transition matrix F(dt) for constant-velocity model."""
    F = np.eye(8, dtype=np.float64)
    F[0, 4] = dt
    F[1, 5] = dt
    F[2, 6] = dt
    F[3, 7] = dt
    return F


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class FusedTrack:
    """
    A fused track combining edge detection and identity recognition.

    Kalman state is 8-dimensional: [cx, cy, w, h, vx, vy, vw, vh]
    where (cx, cy) is center, (w, h) is size, and v* are velocities.
    """

    track_id: int
    edge_track_id: int
    user_id: str | None = None
    name: str | None = None
    student_id: str | None = None
    similarity: float | None = None
    confidence: float = 0.0
    missed_frames: int = 0
    is_confirmed: bool = False
    detection_count: int = 0

    _state: np.ndarray = field(default_factory=lambda: np.zeros(8, dtype=np.float64))
    _covariance: np.ndarray = field(
        default_factory=lambda: np.eye(8, dtype=np.float64) * 100.0
    )
    _last_update: float = field(default_factory=time.time)

    @property
    def bbox(self) -> list[float]:
        """Return [x, y, w, h] from Kalman state (cx - w/2, cy - h/2, w, h)."""
        cx, cy, w, h = self._state[:4]
        return [
            round(cx - w / 2, 1),
            round(cy - h / 2, 1),
            round(max(w, 1), 1),
            round(max(h, 1), 1),
        ]

    def to_dict(self) -> dict:
        """Return all public fields as a dictionary."""
        return {
            "track_id": self.track_id,
            "edge_track_id": self.edge_track_id,
            "user_id": self.user_id,
            "name": self.name,
            "student_id": self.student_id,
            "similarity": self.similarity,
            "confidence": round(self.confidence, 2),
            "missed_frames": self.missed_frames,
            "state": "confirmed" if self.is_confirmed else "tentative",
            "bbox": self.bbox,
        }


@dataclass
class RoomState:
    """Per-room tracking state."""

    tracks: dict[int, FusedTrack] = field(default_factory=dict)
    edge_to_fused: dict[int, int] = field(default_factory=dict)
    next_fused_id: int = 1
    frame_width: int = 0
    frame_height: int = 0
    update_seq: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)
    # Recently removed tracks for identity inheritance (fused_id → FusedTrack)
    _graveyard: dict[int, FusedTrack] = field(default_factory=dict)
    _graveyard_ts: dict[int, float] = field(default_factory=dict)  # fused_id → removal time


# ── Kalman helpers ───────────────────────────────────────────────────────────


def _kalman_predict(track: FusedTrack, dt: float) -> None:
    """Predict-only step: advance state forward by dt."""
    F = _make_F(dt)
    track._state = F @ track._state
    track._covariance = F @ track._covariance @ F.T + Q_BASE * dt


def _kalman_update(track: FusedTrack, measurement: np.ndarray, dt: float) -> None:
    """Full predict + update step with a measurement [cx, cy, w, h]."""
    F = _make_F(dt)

    # Predict
    predicted_state = F @ track._state
    predicted_cov = F @ track._covariance @ F.T + Q_BASE * dt

    # Update
    y = measurement - H @ predicted_state
    S = H @ predicted_cov @ H.T + R
    K = predicted_cov @ H.T @ np.linalg.inv(S)

    track._state = predicted_state + K @ y
    track._covariance = (np.eye(8) - K @ H) @ predicted_cov
    track._last_update = time.time()


def _bbox_to_measurement(bbox: list[float]) -> np.ndarray:
    """Convert [x, y, w, h] to measurement [cx, cy, w, h]."""
    x, y, w, h = bbox
    return np.array([x + w / 2, y + h / 2, w, h], dtype=np.float64)


# ── Service ──────────────────────────────────────────────────────────────────


class TrackFusionService:
    """
    Fuses edge detections and backend identity recognition into smooth
    Kalman-predicted tracks, one state per room.
    """

    def __init__(self, max_missed_frames: int = 8, confirm_threshold: int = 3):
        self.max_missed_frames = max_missed_frames
        self.confirm_threshold = confirm_threshold
        self._rooms: dict[str, RoomState] = {}
        self._rooms_lock = threading.Lock()

    def _get_room(self, room_id: str) -> RoomState:
        """Get or create room state (thread-safe)."""
        with self._rooms_lock:
            if room_id not in self._rooms:
                self._rooms[room_id] = RoomState()
            return self._rooms[room_id]

    def update_from_edge(
        self,
        room_id: str,
        detections: list[dict],
        frame_width: int,
        frame_height: int,
    ) -> None:
        """
        Process edge detections for a room.

        Each detection dict has: track_id, bbox [x,y,w,h], confidence.
        Matches to existing tracks via edge_track_id mapping.
        """
        room = self._get_room(room_id)

        with room.lock:
            room.frame_width = frame_width
            room.frame_height = frame_height

            now = time.time()
            seen_edge_ids: set[int] = set()

            for det in detections:
                edge_tid = det["track_id"]
                bbox = det["bbox"]
                conf = det["confidence"]
                measurement = _bbox_to_measurement(bbox)
                seen_edge_ids.add(edge_tid)

                if edge_tid in room.edge_to_fused:
                    # Matched — update existing track
                    fused_id = room.edge_to_fused[edge_tid]
                    track = room.tracks[fused_id]
                    dt = now - track._last_update
                    dt = max(dt, 1e-4)  # guard against zero

                    _kalman_update(track, measurement, dt)
                    track.confidence = conf
                    track.missed_frames = 0
                    track.detection_count += 1
                    track.is_confirmed = (
                        track.detection_count >= self.confirm_threshold
                    )
                else:
                    # New track
                    fused_id = room.next_fused_id
                    room.next_fused_id += 1

                    track = FusedTrack(
                        track_id=fused_id,
                        edge_track_id=edge_tid,
                        confidence=conf,
                        detection_count=1,
                        _last_update=now,
                    )
                    # Seed state from measurement + edge velocity
                    vel = det.get("velocity", [0.0, 0.0])
                    track._state = np.array(
                        [measurement[0], measurement[1], measurement[2], measurement[3],
                         vel[0], vel[1], 0.0, 0.0],
                        dtype=np.float64,
                    )
                    track._covariance = np.eye(8, dtype=np.float64) * 100.0

                    # Inherit identity from recently-removed nearby track
                    best_grave_dist = 150.0  # max px distance
                    best_grave_id = None
                    cx, cy = measurement[0], measurement[1]
                    for gid, gtrak in room._graveyard.items():
                        gcx, gcy = gtrak._state[0], gtrak._state[1]
                        dist = ((cx - gcx) ** 2 + (cy - gcy) ** 2) ** 0.5
                        if dist < best_grave_dist:
                            best_grave_dist = dist
                            best_grave_id = gid
                    if best_grave_id is not None:
                        donor = room._graveyard.pop(best_grave_id)
                        room._graveyard_ts.pop(best_grave_id, None)
                        track.user_id = donor.user_id
                        track.name = donor.name
                        track.student_id = donor.student_id
                        track.similarity = donor.similarity

                    room.tracks[fused_id] = track
                    room.edge_to_fused[edge_tid] = fused_id

            # Increment missed_frames for unmatched tracks and delete stale ones
            stale_ids = []
            for fused_id, track in room.tracks.items():
                if track.edge_track_id not in seen_edge_ids:
                    track.missed_frames += 1
                    if track.missed_frames > self.max_missed_frames:
                        stale_ids.append(fused_id)

            for fused_id in stale_ids:
                track = room.tracks.pop(fused_id)
                room.edge_to_fused.pop(track.edge_track_id, None)
                # Store in graveyard for identity inheritance (keep for 5s)
                if track.user_id:
                    room._graveyard[fused_id] = track
                    room._graveyard_ts[fused_id] = now

            # Purge graveyard entries older than 5 seconds
            expired = [
                fid for fid, ts in room._graveyard_ts.items()
                if now - ts > 5.0
            ]
            for fid in expired:
                room._graveyard.pop(fid, None)
                room._graveyard_ts.pop(fid, None)

            room.update_seq += 1

    def update_identity(
        self,
        room_id: str,
        edge_track_id: int,
        user_id: str,
        name: str,
        student_id: str,
        similarity: float,
    ) -> None:
        """
        Update identity for a track. Only updates if similarity is better
        than existing or no identity exists yet.
        """
        room = self._get_room(room_id)

        with room.lock:
            fused_id = room.edge_to_fused.get(edge_track_id)
            if fused_id is None:
                logger.warning(
                    "update_identity: edge_track_id %d not found in room %s",
                    edge_track_id,
                    room_id,
                )
                return

            track = room.tracks[fused_id]
            if track.similarity is None or similarity > track.similarity:
                track.user_id = user_id
                track.name = name
                track.student_id = student_id
                track.similarity = similarity

    def predict(self, room_id: str, dt: float) -> None:
        """Advance all Kalman filters forward by dt (predict-only, no measurement)."""
        room = self._rooms.get(room_id)
        if room is None:
            return

        with room.lock:
            for track in room.tracks.values():
                _kalman_predict(track, dt)

    def get_update_seq(self, room_id: str) -> int:
        """Return the current update sequence number for a room."""
        room = self._rooms.get(room_id)
        if room is None:
            return 0
        with room.lock:
            return room.update_seq

    def get_tracks(self, room_id: str) -> list[dict]:
        """Return all tracks for a room as dicts."""
        room = self._rooms.get(room_id)
        if room is None:
            return []

        with room.lock:
            return [track.to_dict() for track in room.tracks.values()]

    def get_room_dimensions(self, room_id: str) -> tuple[int, int]:
        """Return (frame_width, frame_height) for a room."""
        room = self._rooms.get(room_id)
        if room is None:
            return (0, 0)

        with room.lock:
            return (room.frame_width, room.frame_height)

    def cleanup_room(self, room_id: str) -> None:
        """Remove all state for a room."""
        with self._rooms_lock:
            self._rooms.pop(room_id, None)
