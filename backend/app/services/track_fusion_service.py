# backend/app/services/track_fusion_service.py
"""
Track Fusion Engine — Merges detections + recognitions into smooth 30 FPS output.

Runs as a background task inside the API Gateway container.
Consumes: stream:detections:{room_id}, stream:recognitions
Provides: get_tracks(room_id) for WebSocket broadcaster
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field

import numpy as np

from app.config import settings
from app.services.stream_bus import (
    STREAM_DETECTIONS,
    STREAM_RECOGNITIONS,
    get_stream_bus,
)

logger = logging.getLogger(__name__)


@dataclass
class FusedTrack:
    track_id: int
    bbox: list[float]  # [x1, y1, x2, y2] normalized 0-1
    confidence: float
    state: str  # "tentative" | "confirmed" | "lost"
    hit_count: int = 0
    lost_count: int = 0
    last_update: float = 0.0
    # Identity (filled by recognition stream)
    user_id: str | None = None
    name: str | None = None
    student_id: str | None = None
    similarity: float | None = None
    # Kalman state
    kalman_state: np.ndarray | None = None
    kalman_cov: np.ndarray | None = None


class TrackFusionEngine:
    """Fuses detections and recognitions into smooth, identified tracks."""

    def __init__(self):
        self.rooms: dict[str, dict[int, FusedTrack]] = {}  # room_id -> {track_id -> track}
        self._running = False
        self._task: asyncio.Task | None = None
        # Kalman matrices (shared across all tracks)
        self._dt = 1.0 / settings.FUSION_OUTPUT_FPS
        self._init_kalman_matrices()

    def _init_kalman_matrices(self):
        """8-dim Kalman: [cx, cy, w, h, vx, vy, vw, vh]"""
        dt = self._dt
        self.F = np.eye(8)
        self.F[0, 4] = dt
        self.F[1, 5] = dt
        self.F[2, 6] = dt
        self.F[3, 7] = dt
        self.H = np.zeros((4, 8))
        self.H[0, 0] = 1
        self.H[1, 1] = 1
        self.H[2, 2] = 1
        self.H[3, 3] = 1
        self.Q = np.eye(8) * 1.0
        self.Q[4:, 4:] *= 0.1  # Low velocity noise (seated students)
        self.R = np.eye(4) * 4.0  # Trust detections closely

    async def start(self, room_ids: list[str] | None = None):
        """Start consuming detection and recognition streams."""
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("[track-fusion] Started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[track-fusion] Stopped")

    async def _consume_loop(self):
        """Background task consuming detection and recognition streams."""
        bus = await get_stream_bus()

        # We'll poll for detection streams dynamically
        det_group = "track-fusion"
        rec_group = "track-fusion"

        await bus.ensure_group(STREAM_RECOGNITIONS, rec_group)

        while self._running:
            try:
                # Discover detection streams
                r = bus.redis
                det_streams = []
                async for key in r.scan_iter(match=b"stream:detections:*"):
                    key_str = key.decode() if isinstance(key, bytes) else key
                    det_streams.append(key_str)
                    await bus.ensure_group(key_str, det_group)

                if not det_streams:
                    await asyncio.sleep(0.5)
                    continue

                # Build stream dict
                streams = {s: ">" for s in det_streams}
                streams[STREAM_RECOGNITIONS] = ">"

                messages = await bus.consume_multiple(
                    streams=streams,
                    group=det_group,
                    consumer="fusion-1",
                    count=10,
                    block=100,  # 100ms block for responsive fusion
                )

                for stream, msg_id, data in messages:
                    if "detections" in stream:
                        self._handle_detections(data)
                    elif "recognitions" in stream:
                        self._handle_recognition(data)
                    await bus.ack(stream, det_group, msg_id)

                # Predict step for all rooms (Kalman coast)
                self._predict_all()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[track-fusion] Error: {e}", exc_info=True)
                await asyncio.sleep(0.5)

    def _handle_detections(self, data: dict):
        """Update tracks from detection worker output."""
        room_id = data.get("room_id", "unknown")
        detections = data.get("detections", [])
        now = time.time()

        if room_id not in self.rooms:
            self.rooms[room_id] = {}

        tracks = self.rooms[room_id]

        # Update existing tracks and create new ones
        seen_track_ids = set()
        for det in detections:
            tid = det.get("track_id", -1)
            bbox = det.get("bbox", [0, 0, 0, 0])
            conf = det.get("confidence", 0.0)
            is_new = det.get("is_new", False)
            seen_track_ids.add(tid)

            if tid in tracks:
                track = tracks[tid]
                track.bbox = bbox
                track.confidence = conf
                track.hit_count += 1
                track.lost_count = 0
                track.last_update = now
                if track.state == "tentative" and track.hit_count >= settings.TRACK_CONFIRM_HITS:
                    track.state = "confirmed"
                elif track.state == "lost":
                    track.state = "confirmed"
                # Kalman update
                self._kalman_update(track, bbox)
            elif is_new:
                track = FusedTrack(
                    track_id=tid,
                    bbox=bbox,
                    confidence=conf,
                    state="tentative",
                    hit_count=1,
                    last_update=now,
                )
                self._kalman_init(track, bbox)
                tracks[tid] = track

        # Mark unseen tracks as losing
        for tid, track in list(tracks.items()):
            if tid not in seen_track_ids:
                track.lost_count += 1
                coast_ms = settings.TRACK_COAST_MS
                delete_ms = settings.TRACK_DELETE_MS
                elapsed_ms = (now - track.last_update) * 1000

                if elapsed_ms > delete_ms:
                    del tracks[tid]
                elif elapsed_ms > coast_ms and track.state != "lost":
                    track.state = "lost"

    def _handle_recognition(self, data: dict):
        """Merge identity from recognition worker into a track."""
        room_id = data.get("room_id", "unknown")
        track_id = data.get("track_id", -1)

        if room_id not in self.rooms:
            return

        track = self.rooms[room_id].get(track_id)
        if track:
            track.user_id = data.get("user_id")
            track.name = data.get("name")
            track.student_id = data.get("student_id")
            track.similarity = data.get("similarity")

    def _predict_all(self):
        """Kalman predict step for all active tracks."""
        for room_id, tracks in self.rooms.items():
            for track in tracks.values():
                if track.kalman_state is not None:
                    self._kalman_predict(track)

    def _kalman_init(self, track: FusedTrack, bbox: list[float]):
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        track.kalman_state = np.array([cx, cy, w, h, 0, 0, 0, 0], dtype=float)
        track.kalman_cov = np.eye(8) * 10.0

    def _kalman_predict(self, track: FusedTrack):
        if track.kalman_state is None:
            return
        track.kalman_state = self.F @ track.kalman_state
        track.kalman_cov = self.F @ track.kalman_cov @ self.F.T + self.Q
        # Update bbox from predicted state
        s = track.kalman_state
        track.bbox = [s[0] - s[2] / 2, s[1] - s[3] / 2, s[0] + s[2] / 2, s[1] + s[3] / 2]

    def _kalman_update(self, track: FusedTrack, bbox: list[float]):
        if track.kalman_state is None:
            self._kalman_init(track, bbox)
            return
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        z = np.array([cx, cy, w, h])
        S = self.H @ track.kalman_cov @ self.H.T + self.R
        K = track.kalman_cov @ self.H.T @ np.linalg.inv(S)
        track.kalman_state = track.kalman_state + K @ (z - self.H @ track.kalman_state)
        track.kalman_cov = (np.eye(8) - K @ self.H) @ track.kalman_cov
        # Update bbox from corrected state
        s = track.kalman_state
        track.bbox = [s[0] - s[2] / 2, s[1] - s[3] / 2, s[0] + s[2] / 2, s[1] + s[3] / 2]

    def get_tracks(self, room_id: str) -> list[dict]:
        """Get current fused tracks for a room (called by WebSocket broadcaster)."""
        tracks = self.rooms.get(room_id, {})
        result = []
        for track in tracks.values():
            if track.state == "lost":
                continue  # Don't send lost tracks to mobile
            entry = {
                "id": track.track_id,
                "bbox": track.bbox,
                "conf": track.confidence,
                "state": track.state,
            }
            if track.user_id:
                entry["identity"] = {
                    "user_id": track.user_id,
                    "name": track.name,
                    "student_id": track.student_id,
                    "similarity": track.similarity,
                }
            result.append(entry)
        return result

    def get_identified_users(self, room_id: str) -> dict[str, dict]:
        """Get all identified users in a room. Used by presence engine."""
        tracks = self.rooms.get(room_id, {})
        users = {}
        for track in tracks.values():
            if track.user_id and track.state == "confirmed":
                users[track.user_id] = {
                    "name": track.name,
                    "student_id": track.student_id,
                    "similarity": track.similarity,
                    "track_id": track.track_id,
                }
        return users


# Singleton
_engine: TrackFusionEngine | None = None


def get_track_fusion_engine() -> TrackFusionEngine:
    global _engine
    if _engine is None:
        _engine = TrackFusionEngine()
    return _engine
