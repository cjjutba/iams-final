# Layered Bounding Box Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Seamless 30 FPS bounding box tracking over CCTV live stream supporting 50+ simultaneous faces using a three-tier layered pipeline (RPi centroid tracker → VPS Kalman fusion → Mobile spring animation).

**Architecture:** RPi adds a lightweight centroid tracker to assign stable track IDs at 15 FPS. VPS fuses edge detections with ArcFace identity results via per-track Kalman filters, upsampling to 30 FPS. Mobile receives pre-smoothed tracks and renders with GPU-accelerated spring animation.

**Tech Stack:** Python (NumPy, SciPy for Kalman), FastAPI WebSocket, React Native Animated API

**Design Doc:** `docs/plans/2026-03-15-layered-bbox-tracking-design.md`

---

## Task 1: RPi Centroid Tracker

**Files:**
- Create: `edge/app/centroid_tracker.py`
- Test: Manual testing on RPi (no pytest infrastructure on edge)

### Step 1: Create CentroidTracker class

Create `edge/app/centroid_tracker.py`:

```python
"""Lightweight centroid tracker for stable track IDs across frames.

Uses Euclidean distance between bounding box centroids to associate
detections across consecutive frames. Designed for stationary cameras
where faces move gradually (~50px/frame max).
"""

import numpy as np
from dataclasses import dataclass, field


@dataclass
class TrackedObject:
    track_id: int
    centroid: tuple[float, float]
    bbox: list[int]  # [x, y, w, h]
    confidence: float
    frames_since_seen: int = 0
    prev_centroid: tuple[float, float] | None = None

    @property
    def velocity(self) -> tuple[float, float]:
        if self.prev_centroid is None:
            return (0.0, 0.0)
        return (
            self.centroid[0] - self.prev_centroid[0],
            self.centroid[1] - self.prev_centroid[1],
        )


class CentroidTracker:
    """Assign stable track IDs to detections using centroid distance matching.

    Args:
        max_disappeared: Consecutive frames a track can be missing before deletion.
        max_distance: Maximum centroid distance (px) to consider a match.
    """

    def __init__(self, max_disappeared: int = 5, max_distance: float = 50.0):
        self._next_id = 0
        self._tracks: dict[int, TrackedObject] = {}
        self._max_disappeared = max_disappeared
        self._max_distance = max_distance
        self._frame_seq = 0

    @property
    def frame_seq(self) -> int:
        return self._frame_seq

    def update(self, detections: list[dict]) -> list[TrackedObject]:
        """Match new detections to existing tracks and return updated tracks.

        Args:
            detections: List of dicts with 'bbox' [x, y, w, h] and 'confidence'.

        Returns:
            List of TrackedObject with stable track_ids.
        """
        self._frame_seq += 1

        # Compute centroids for incoming detections
        input_centroids = []
        for det in detections:
            bx, by, bw, bh = det["bbox"]
            cx = bx + bw / 2.0
            cy = by + bh / 2.0
            input_centroids.append((cx, cy))

        # No existing tracks — register all as new
        if len(self._tracks) == 0:
            for i, det in enumerate(detections):
                self._register(input_centroids[i], det["bbox"], det["confidence"])
            return list(self._tracks.values())

        # No new detections — mark all existing as disappeared
        if len(detections) == 0:
            self._mark_all_disappeared()
            return list(self._tracks.values())

        # Compute distance matrix: existing tracks vs new detections
        track_ids = list(self._tracks.keys())
        track_centroids = np.array(
            [self._tracks[tid].centroid for tid in track_ids]
        )
        det_centroids = np.array(input_centroids)

        # Euclidean distance matrix [num_tracks x num_detections]
        diff = track_centroids[:, np.newaxis, :] - det_centroids[np.newaxis, :, :]
        dist_matrix = np.sqrt((diff ** 2).sum(axis=2))

        # Greedy nearest-neighbor matching
        matched_tracks = set()
        matched_dets = set()

        # Sort all pairs by distance, match greedily
        rows, cols = np.unravel_index(
            np.argsort(dist_matrix, axis=None), dist_matrix.shape
        )

        for row, col in zip(rows, cols):
            if row in matched_tracks or col in matched_dets:
                continue
            if dist_matrix[row, col] > self._max_distance:
                break
            tid = track_ids[row]
            track = self._tracks[tid]
            track.prev_centroid = track.centroid
            track.centroid = input_centroids[col]
            track.bbox = detections[col]["bbox"]
            track.confidence = detections[col]["confidence"]
            track.frames_since_seen = 0
            matched_tracks.add(row)
            matched_dets.add(col)

        # Unmatched tracks — increment disappeared count
        for row in range(len(track_ids)):
            if row not in matched_tracks:
                tid = track_ids[row]
                self._tracks[tid].frames_since_seen += 1
                if self._tracks[tid].frames_since_seen > self._max_disappeared:
                    del self._tracks[tid]

        # Unmatched detections — register as new tracks
        for col in range(len(detections)):
            if col not in matched_dets:
                self._register(
                    input_centroids[col],
                    detections[col]["bbox"],
                    detections[col]["confidence"],
                )

        return list(self._tracks.values())

    def reset(self):
        """Clear all tracks and reset state."""
        self._tracks.clear()
        self._next_id = 0
        self._frame_seq = 0

    def _register(self, centroid, bbox, confidence):
        self._tracks[self._next_id] = TrackedObject(
            track_id=self._next_id,
            centroid=centroid,
            bbox=bbox,
            confidence=confidence,
        )
        self._next_id += 1
        # Wrap at 65535 to avoid unbounded growth
        if self._next_id > 65535:
            self._next_id = 0

    def _mark_all_disappeared(self):
        to_delete = []
        for tid, track in self._tracks.items():
            track.frames_since_seen += 1
            if track.frames_since_seen > self._max_disappeared:
                to_delete.append(tid)
        for tid in to_delete:
            del self._tracks[tid]
```

### Step 2: Verify file created

Run: `python -c "from app.centroid_tracker import CentroidTracker; print('OK')"` from `edge/` directory.
Expected: `OK`

### Step 3: Commit

```bash
git add edge/app/centroid_tracker.py
git commit -m "feat(edge): add centroid tracker for stable face track IDs"
```

---

## Task 2: Integrate Centroid Tracker into Edge Detection Loop

**Files:**
- Modify: `edge/app/detector.py` (import and use CentroidTracker after detection)
- Modify: `edge/app/edge_websocket.py` (add frame_seq, centroid, velocity to message)

### Step 1: Add CentroidTracker to FaceDetector

In `edge/app/detector.py`, add import at top:

```python
from app.centroid_tracker import CentroidTracker
```

In `FaceDetector.__init__()` (around line 119), add:

```python
self._centroid_tracker = CentroidTracker(max_disappeared=5, max_distance=50.0)
```

Add a new method after `detect()`:

```python
def detect_and_track(self, frame: np.ndarray) -> tuple[list, list]:
    """Detect faces and assign stable track IDs via centroid tracking.

    Returns:
        Tuple of (face_boxes, tracked_objects) where tracked_objects
        have stable track_id, centroid, and velocity.
    """
    faces = self.detect(frame)
    if not faces:
        tracked = self._centroid_tracker.update([])
        return faces, tracked

    detections = [
        {"bbox": [f.x, f.y, f.width, f.height], "confidence": f.confidence}
        for f in faces
    ]
    tracked = self._centroid_tracker.update(detections)
    return faces, tracked

@property
def frame_seq(self) -> int:
    return self._centroid_tracker.frame_seq
```

### Step 2: Update edge_websocket.py message format

In `edge/app/edge_websocket.py`, modify `send_detections()` (around line 104) to accept tracked objects. Add a new method:

```python
def send_tracked_detections(
    self,
    tracked_objects: list,
    frame_width: int,
    frame_height: int,
    frame_seq: int,
) -> None:
    """Send tracked detections with centroid and velocity data."""
    if not self._connected:
        return

    detections = []
    for t in tracked_objects:
        detections.append({
            "track_id": t.track_id,
            "bbox": t.bbox,
            "confidence": t.confidence,
            "centroid": list(t.centroid),
            "velocity": list(t.velocity),
        })

    message = {
        "type": "edge_detections",
        "room_id": self._room_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "frame_seq": frame_seq,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "detections": detections,
    }

    try:
        self._queue.put_nowait(message)
    except Exception:
        pass  # Drop frame if queue full
```

### Step 3: Update the main detection loop caller

Find where `detector.detect()` is called and `edge_ws.send_detections()` is invoked in the main loop (likely in `edge/app/processor.py` or `edge/run.py`). Update the call site to use `detect_and_track()` and `send_tracked_detections()` instead:

```python
# Before:
# faces = detector.detect(frame)
# edge_ws.send_detections(detections_list, width, height)

# After:
faces, tracked = detector.detect_and_track(frame)
edge_ws.send_tracked_detections(tracked, width, height, detector.frame_seq)
```

Keep the existing `send_detections()` method for backward compatibility — it can be removed later.

### Step 4: Test on RPi

Run the edge device and verify WebSocket messages now include `frame_seq`, `centroid`, and `velocity` fields. Check VPS backend logs for incoming messages.

### Step 5: Commit

```bash
git add edge/app/detector.py edge/app/edge_websocket.py
git commit -m "feat(edge): integrate centroid tracker into detection loop"
```

---

## Task 3: VPS TrackFusionService — Kalman Filter Core

**Files:**
- Create: `backend/app/services/track_fusion_service.py`
- Test: `backend/tests/test_track_fusion.py`

### Step 1: Write failing tests

Create `backend/tests/test_track_fusion.py`:

```python
"""Tests for TrackFusionService Kalman filter and track fusion."""

import pytest
import asyncio
from unittest.mock import AsyncMock
from app.services.track_fusion_service import TrackFusionService, FusedTrack


@pytest.fixture
def service():
    return TrackFusionService()


class TestFusedTrackCreation:
    def test_new_track_from_edge_detection(self, service):
        detections = [
            {
                "track_id": 1,
                "bbox": [100, 100, 80, 100],
                "confidence": 0.9,
                "centroid": [140.0, 150.0],
                "velocity": [0.0, 0.0],
            }
        ]
        service.update_from_edge("room-1", detections, 640, 480)
        tracks = service.get_tracks("room-1")
        assert len(tracks) == 1
        assert tracks[0]["edge_track_id"] == 1
        assert tracks[0]["bbox"][0] == pytest.approx(100, abs=1)

    def test_track_persists_across_updates(self, service):
        det1 = [{"track_id": 1, "bbox": [100, 100, 80, 100], "confidence": 0.9,
                 "centroid": [140.0, 150.0], "velocity": [2.0, 0.0]}]
        det2 = [{"track_id": 1, "bbox": [104, 100, 80, 100], "confidence": 0.9,
                 "centroid": [144.0, 150.0], "velocity": [2.0, 0.0]}]
        service.update_from_edge("room-1", det1, 640, 480)
        service.update_from_edge("room-1", det2, 640, 480)
        tracks = service.get_tracks("room-1")
        assert len(tracks) == 1  # Same track, not duplicated


class TestIdentityFusion:
    def test_identity_merges_into_track(self, service):
        det = [{"track_id": 1, "bbox": [100, 100, 80, 100], "confidence": 0.9,
                "centroid": [140.0, 150.0], "velocity": [0.0, 0.0]}]
        service.update_from_edge("room-1", det, 640, 480)
        service.update_identity("room-1", edge_track_id=1,
                                user_id="user-123", name="Juan",
                                student_id="22-00456", similarity=0.87)
        tracks = service.get_tracks("room-1")
        assert tracks[0]["user_id"] == "user-123"
        assert tracks[0]["name"] == "Juan"

    def test_identity_is_sticky(self, service):
        det = [{"track_id": 1, "bbox": [100, 100, 80, 100], "confidence": 0.9,
                "centroid": [140.0, 150.0], "velocity": [0.0, 0.0]}]
        service.update_from_edge("room-1", det, 640, 480)
        service.update_identity("room-1", edge_track_id=1,
                                user_id="user-123", name="Juan",
                                student_id="22-00456", similarity=0.87)
        # Update without identity — should retain
        det2 = [{"track_id": 1, "bbox": [104, 100, 80, 100], "confidence": 0.9,
                 "centroid": [144.0, 150.0], "velocity": [2.0, 0.0]}]
        service.update_from_edge("room-1", det2, 640, 480)
        tracks = service.get_tracks("room-1")
        assert tracks[0]["user_id"] == "user-123"


class TestKalmanPrediction:
    def test_predict_advances_position(self, service):
        det = [{"track_id": 1, "bbox": [100, 100, 80, 100], "confidence": 0.9,
                "centroid": [140.0, 150.0], "velocity": [5.0, 0.0]}]
        service.update_from_edge("room-1", det, 640, 480)
        # Predict forward without new measurement
        service.predict("room-1", dt=0.033)  # 33ms
        tracks = service.get_tracks("room-1")
        # Position should have moved slightly based on velocity
        assert tracks[0]["bbox"][0] >= 100

    def test_predict_with_no_tracks_is_noop(self, service):
        service.predict("room-1", dt=0.033)
        tracks = service.get_tracks("room-1")
        assert len(tracks) == 0


class TestTrackDeletion:
    def test_track_removed_after_max_missed(self, service):
        det = [{"track_id": 1, "bbox": [100, 100, 80, 100], "confidence": 0.9,
                "centroid": [140.0, 150.0], "velocity": [0.0, 0.0]}]
        service.update_from_edge("room-1", det, 640, 480)
        # Send 11 empty updates (max_missed_frames=10)
        for _ in range(11):
            service.update_from_edge("room-1", [], 640, 480)
        tracks = service.get_tracks("room-1")
        assert len(tracks) == 0


class TestMultipleRooms:
    def test_rooms_are_independent(self, service):
        det1 = [{"track_id": 1, "bbox": [100, 100, 80, 100], "confidence": 0.9,
                 "centroid": [140.0, 150.0], "velocity": [0.0, 0.0]}]
        det2 = [{"track_id": 1, "bbox": [200, 200, 60, 80], "confidence": 0.8,
                 "centroid": [230.0, 240.0], "velocity": [0.0, 0.0]}]
        service.update_from_edge("room-1", det1, 640, 480)
        service.update_from_edge("room-2", det2, 1280, 720)
        assert len(service.get_tracks("room-1")) == 1
        assert len(service.get_tracks("room-2")) == 1
```

### Step 2: Run tests to verify they fail

Run: `cd backend && pytest tests/test_track_fusion.py -v`
Expected: ImportError or similar — module doesn't exist yet.

### Step 3: Implement TrackFusionService

Create `backend/app/services/track_fusion_service.py`:

```python
"""Track fusion service: merges edge detections + identity into Kalman-predicted tracks.

Receives fast edge detections (15 FPS) and slow identity recognition (2 FPS),
fuses them into smooth 30 FPS output tracks using per-face Kalman filters.
"""

import time
import threading
import numpy as np
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FusedTrack:
    """A single tracked face with fused position and identity."""

    track_id: int
    edge_track_id: int
    # Identity (from recognition, sticky once assigned)
    user_id: str | None = None
    name: str | None = None
    student_id: str | None = None
    similarity: float | None = None
    # Detection
    confidence: float = 0.0
    missed_frames: int = 0
    is_confirmed: bool = False
    detection_count: int = 0
    # Kalman state: [cx, cy, w, h, vx, vy, vw, vh]
    _state: np.ndarray = field(default_factory=lambda: np.zeros(8))
    _covariance: np.ndarray = field(
        default_factory=lambda: np.eye(8) * 100.0
    )
    _last_update: float = field(default_factory=time.time)

    @property
    def bbox(self) -> list[float]:
        """Return [x, y, w, h] from Kalman state [cx, cy, w, h, ...]."""
        cx, cy, w, h = self._state[:4]
        return [
            round(cx - w / 2, 1),
            round(cy - h / 2, 1),
            round(max(w, 1), 1),
            round(max(h, 1), 1),
        ]

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "edge_track_id": self.edge_track_id,
            "bbox": self.bbox,
            "confidence": round(self.confidence, 2),
            "user_id": self.user_id,
            "name": self.name,
            "student_id": self.student_id,
            "similarity": round(self.similarity, 2) if self.similarity else None,
            "state": "confirmed" if self.is_confirmed else "tentative",
            "missed_frames": self.missed_frames,
        }


# Kalman constant-velocity model matrices
def _make_F(dt: float) -> np.ndarray:
    """State transition matrix for constant-velocity model."""
    F = np.eye(8)
    F[0, 4] = dt  # cx += vx * dt
    F[1, 5] = dt  # cy += vy * dt
    F[2, 6] = dt  # w += vw * dt
    F[3, 7] = dt  # h += vh * dt
    return F


# Measurement matrix: we observe [cx, cy, w, h]
_H = np.eye(4, 8)

# Process noise
_Q_BASE = np.diag([1.0, 1.0, 0.5, 0.5, 5.0, 5.0, 1.0, 1.0])

# Measurement noise
_R = np.diag([4.0, 4.0, 4.0, 4.0])


@dataclass
class RoomState:
    """Per-room tracking state."""

    tracks: dict[int, FusedTrack] = field(default_factory=dict)
    edge_to_fused: dict[int, int] = field(default_factory=dict)
    next_fused_id: int = 0
    frame_width: int = 640
    frame_height: int = 480
    lock: threading.Lock = field(default_factory=threading.Lock)


class TrackFusionService:
    """Fuses edge detections + recognition identity via Kalman filters.

    Usage:
        service = TrackFusionService()

        # Called at 15 FPS from edge relay
        service.update_from_edge(room_id, detections, width, height)

        # Called at 2 FPS from recognition service
        service.update_identity(room_id, edge_track_id, user_id, name, ...)

        # Called at 30 FPS by output timer
        service.predict(room_id, dt=0.033)
        tracks = service.get_tracks(room_id)
    """

    def __init__(self, max_missed_frames: int = 10, confirm_threshold: int = 3):
        self._rooms: dict[str, RoomState] = {}
        self._max_missed = max_missed_frames
        self._confirm_threshold = confirm_threshold

    def _get_room(self, room_id: str) -> RoomState:
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
        """Process edge detections: match to existing tracks, create/delete."""
        room = self._get_room(room_id)
        with room.lock:
            room.frame_width = frame_width
            room.frame_height = frame_height
            now = time.time()

            matched_fused_ids = set()

            for det in detections:
                edge_tid = det["track_id"]
                bx, by, bw, bh = det["bbox"]
                cx = bx + bw / 2.0
                cy = by + bh / 2.0
                measurement = np.array([cx, cy, float(bw), float(bh)])

                if edge_tid in room.edge_to_fused:
                    fused_id = room.edge_to_fused[edge_tid]
                    if fused_id in room.tracks:
                        track = room.tracks[fused_id]
                        dt = max(now - track._last_update, 0.001)
                        self._kalman_update(track, measurement, dt)
                        track.confidence = det["confidence"]
                        track.missed_frames = 0
                        track.detection_count += 1
                        track._last_update = now
                        if track.detection_count >= self._confirm_threshold:
                            track.is_confirmed = True
                        matched_fused_ids.add(fused_id)
                        continue

                # New track
                fused_id = room.next_fused_id
                room.next_fused_id += 1
                state = np.zeros(8)
                state[:4] = measurement
                # Seed velocity from edge if available
                vel = det.get("velocity", [0.0, 0.0])
                state[4] = vel[0]
                state[5] = vel[1]

                track = FusedTrack(
                    track_id=fused_id,
                    edge_track_id=edge_tid,
                    confidence=det["confidence"],
                    detection_count=1,
                    _state=state,
                    _covariance=np.eye(8) * 100.0,
                    _last_update=now,
                )
                room.tracks[fused_id] = track
                room.edge_to_fused[edge_tid] = fused_id
                matched_fused_ids.add(fused_id)

            # Increment missed_frames for unmatched tracks, delete stale ones
            to_delete = []
            for fused_id, track in room.tracks.items():
                if fused_id not in matched_fused_ids:
                    track.missed_frames += 1
                    if track.missed_frames > self._max_missed:
                        to_delete.append(fused_id)

            for fused_id in to_delete:
                track = room.tracks.pop(fused_id)
                # Clean up edge mapping
                room.edge_to_fused = {
                    k: v for k, v in room.edge_to_fused.items() if v != fused_id
                }

    def update_identity(
        self,
        room_id: str,
        edge_track_id: int,
        user_id: str,
        name: str,
        student_id: str,
        similarity: float,
    ) -> None:
        """Merge identity from recognition into a fused track."""
        room = self._get_room(room_id)
        with room.lock:
            fused_id = room.edge_to_fused.get(edge_track_id)
            if fused_id is None or fused_id not in room.tracks:
                return
            track = room.tracks[fused_id]
            # Only update if better similarity or no existing identity
            if track.user_id is None or (
                track.similarity is not None and similarity > track.similarity
            ):
                track.user_id = user_id
                track.name = name
                track.student_id = student_id
                track.similarity = similarity

    def predict(self, room_id: str, dt: float) -> None:
        """Advance all Kalman filters forward by dt seconds (no measurement)."""
        room = self._rooms.get(room_id)
        if room is None:
            return
        with room.lock:
            F = _make_F(dt)
            Q = _Q_BASE * dt
            for track in room.tracks.values():
                track._state = F @ track._state
                track._covariance = F @ track._covariance @ F.T + Q

    def get_tracks(self, room_id: str) -> list[dict]:
        """Return all current tracks as dicts for WebSocket output."""
        room = self._rooms.get(room_id)
        if room is None:
            return []
        with room.lock:
            return [t.to_dict() for t in room.tracks.values()]

    def get_room_dimensions(self, room_id: str) -> tuple[int, int]:
        """Return (frame_width, frame_height) for a room."""
        room = self._rooms.get(room_id)
        if room is None:
            return 640, 480
        return room.frame_width, room.frame_height

    def cleanup_room(self, room_id: str) -> None:
        """Remove all state for a room."""
        self._rooms.pop(room_id, None)

    @staticmethod
    def _kalman_update(
        track: FusedTrack, measurement: np.ndarray, dt: float
    ) -> None:
        """Kalman predict + update step."""
        # Predict
        F = _make_F(dt)
        Q = _Q_BASE * dt
        predicted_state = F @ track._state
        predicted_cov = F @ track._covariance @ F.T + Q

        # Update
        y = measurement - _H @ predicted_state  # Innovation
        S = _H @ predicted_cov @ _H.T + _R  # Innovation covariance
        K = predicted_cov @ _H.T @ np.linalg.inv(S)  # Kalman gain

        track._state = predicted_state + K @ y
        track._covariance = (np.eye(8) - K @ _H) @ predicted_cov
```

### Step 4: Run tests to verify they pass

Run: `cd backend && pytest tests/test_track_fusion.py -v`
Expected: All tests PASS.

### Step 5: Commit

```bash
git add backend/app/services/track_fusion_service.py backend/tests/test_track_fusion.py
git commit -m "feat(backend): add TrackFusionService with Kalman filter for track fusion"
```

---

## Task 4: Wire TrackFusionService into Edge Relay

**Files:**
- Modify: `backend/app/services/edge_relay_service.py` (route edge detections through fusion)
- Modify: `backend/app/routers/live_stream.py` (output fused_tracks instead of raw detections)

### Step 1: Instantiate TrackFusionService as singleton

In `backend/app/services/edge_relay_service.py`, add import and singleton at module level:

```python
from app.services.track_fusion_service import TrackFusionService

track_fusion_service = TrackFusionService()
```

### Step 2: Feed edge detections into fusion service

In `EdgeRelayManager.relay_edge_detections()` (around line 108), add a call to feed detections into the fusion service after the existing relay logic:

```python
# After existing relay logic, feed into fusion
track_fusion_service.update_from_edge(
    room_id,
    message.get("detections", []),
    message.get("frame_width", 640),
    message.get("frame_height", 480),
)
```

### Step 3: Feed identity updates into fusion service

In `EdgeRelayManager.push_identity_update()` (around line 232), after updating `identity_cache`, also update the fusion service:

```python
for mapping in mappings:
    edge_track_id = mapping.get("track_id")
    if edge_track_id is not None:
        try:
            edge_tid = int(edge_track_id) if isinstance(edge_track_id, str) else edge_track_id
            track_fusion_service.update_identity(
                room_id,
                edge_track_id=edge_tid,
                user_id=mapping.get("user_id", ""),
                name=mapping.get("name", ""),
                student_id=mapping.get("student_id", ""),
                similarity=mapping.get("confidence", 0.0),
            )
        except (ValueError, TypeError):
            pass
```

### Step 4: Add 30 FPS fused_tracks output loop in live_stream.py

In `backend/app/routers/live_stream.py`, modify the WebRTC/HLS detection polling loop. Replace the 100ms polling of `recognition_service.get_latest_detections()` with a 33ms loop that calls `track_fusion_service.predict()` and sends `fused_tracks`:

```python
from app.services.edge_relay_service import track_fusion_service

# In the detection loop (WebRTC mode, around line 470):
FUSED_INTERVAL = 1.0 / 30.0  # 33ms for 30 FPS

# Replace existing detection polling with:
last_fused_send = 0
fused_seq = 0

while not stop_event.is_set():
    now = time.time()
    elapsed = now - last_fused_send

    if elapsed >= FUSED_INTERVAL:
        # Predict forward
        track_fusion_service.predict(room_id, dt=elapsed)
        tracks = track_fusion_service.get_tracks(room_id)
        fw, fh = track_fusion_service.get_room_dimensions(room_id)
        fused_seq += 1

        if tracks:
            message = {
                "type": "fused_tracks",
                "room_id": room_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "seq": fused_seq,
                "frame_width": fw,
                "frame_height": fh,
                "tracks": tracks,
            }
            await websocket.send_json(message)

        last_fused_send = now

    # Heartbeat
    if now - last_heartbeat > 5.0:
        await websocket.send_json({
            "type": "heartbeat",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        last_heartbeat = now

    await asyncio.sleep(0.01)  # 10ms sleep to avoid busy loop
```

**Important:** Keep the existing recognition service running — it feeds identity into the fusion service via `push_identity_update()`. Only replace the **output** to mobile with fused_tracks.

### Step 5: Test end-to-end

1. Start backend with a connected edge device
2. Connect mobile to live stream WebSocket
3. Verify mobile receives `fused_tracks` messages at ~30 FPS
4. Verify tracks include identity after recognition kicks in

### Step 6: Commit

```bash
git add backend/app/services/edge_relay_service.py backend/app/routers/live_stream.py
git commit -m "feat(backend): wire TrackFusionService into edge relay and live stream output"
```

---

## Task 5: Mobile TrackAnimationEngine

**Files:**
- Create: `mobile/src/engines/TrackAnimationEngine.ts`

### Step 1: Create the animation engine

Create `mobile/src/engines/TrackAnimationEngine.ts`:

```typescript
/**
 * TrackAnimationEngine: manages per-track Animated values for smooth
 * bounding box rendering at 30 FPS using native-driver spring animation.
 */

import { Animated } from "react-native";

export interface FusedTrack {
  track_id: number;
  bbox: [number, number, number, number]; // [x, y, w, h] floats
  confidence: number;
  user_id: string | null;
  name: string | null;
  student_id: string | null;
  similarity: number | null;
  state: "confirmed" | "tentative";
  missed_frames: number;
}

export interface AnimatedTrack {
  trackId: number;
  x: Animated.Value;
  y: Animated.Value;
  w: Animated.Value;
  h: Animated.Value;
  opacity: Animated.Value;
  userId: string | null;
  name: string | null;
  studentId: string | null;
  similarity: number | null;
  missedFrames: number;
  lastSeen: number; // timestamp
}

const SPRING_CONFIG = {
  stiffness: 300,
  damping: 25,
  mass: 0.8,
  useNativeDriver: false, // layout props (left/top/width/height) can't use native driver
};

const FADE_IN_DURATION = 150;
const FADE_OUT_DURATION = 300;
const STALE_THRESHOLD = 3; // messages without track before fade-out

export class TrackAnimationEngine {
  private tracks: Map<number, AnimatedTrack> = new Map();
  private pool: AnimatedTrack[] = []; // recycled animated values
  private missedCount: Map<number, number> = new Map(); // track_id -> consecutive misses

  /**
   * Update tracks from a fused_tracks WebSocket message.
   * Call this at ~30 FPS.
   */
  update(incomingTracks: FusedTrack[]): AnimatedTrack[] {
    const now = Date.now();
    const seenIds = new Set<number>();

    for (const ft of incomingTracks) {
      seenIds.add(ft.track_id);
      this.missedCount.set(ft.track_id, 0);

      const existing = this.tracks.get(ft.track_id);
      if (existing) {
        // Animate to new position
        this._animateTo(existing.x, ft.bbox[0]);
        this._animateTo(existing.y, ft.bbox[1]);
        this._animateTo(existing.w, ft.bbox[2]);
        this._animateTo(existing.h, ft.bbox[3]);

        // Update metadata (no animation needed)
        existing.userId = ft.user_id;
        existing.name = ft.name;
        existing.studentId = ft.student_id;
        existing.similarity = ft.similarity;
        existing.missedFrames = ft.missed_frames;
        existing.lastSeen = now;

        // Update opacity based on missed_frames
        const targetOpacity = ft.missed_frames > 0 ? 0.5 : 1.0;
        Animated.timing(existing.opacity, {
          toValue: targetOpacity,
          duration: 100,
          useNativeDriver: false,
        }).start();
      } else {
        // Create new track (try pool first)
        const track = this._createTrack(ft, now);
        this.tracks.set(ft.track_id, track);

        // Fade in
        Animated.timing(track.opacity, {
          toValue: ft.missed_frames > 0 ? 0.5 : 1.0,
          duration: FADE_IN_DURATION,
          useNativeDriver: false,
        }).start();
      }
    }

    // Handle tracks not in this message
    for (const [trackId, track] of this.tracks) {
      if (!seenIds.has(trackId)) {
        const missed = (this.missedCount.get(trackId) ?? 0) + 1;
        this.missedCount.set(trackId, missed);

        if (missed >= STALE_THRESHOLD) {
          // Fade out and remove
          Animated.timing(track.opacity, {
            toValue: 0,
            duration: FADE_OUT_DURATION,
            useNativeDriver: false,
          }).start(() => {
            this.tracks.delete(trackId);
            this.missedCount.delete(trackId);
            // Return to pool for reuse
            if (this.pool.length < 20) {
              this.pool.push(track);
            }
          });
        }
      }
    }

    return Array.from(this.tracks.values());
  }

  /** Get current animated tracks for rendering. */
  getAll(): AnimatedTrack[] {
    return Array.from(this.tracks.values());
  }

  /** Clear all tracks (e.g., on disconnect). */
  clear(): void {
    this.tracks.clear();
    this.missedCount.clear();
    this.pool = [];
  }

  private _animateTo(animValue: Animated.Value, target: number): void {
    Animated.spring(animValue, {
      toValue: target,
      ...SPRING_CONFIG,
    }).start();
  }

  private _createTrack(ft: FusedTrack, now: number): AnimatedTrack {
    // Try to reuse from pool
    const recycled = this.pool.pop();
    if (recycled) {
      recycled.trackId = ft.track_id;
      recycled.x.setValue(ft.bbox[0]);
      recycled.y.setValue(ft.bbox[1]);
      recycled.w.setValue(ft.bbox[2]);
      recycled.h.setValue(ft.bbox[3]);
      recycled.opacity.setValue(0);
      recycled.userId = ft.user_id;
      recycled.name = ft.name;
      recycled.studentId = ft.student_id;
      recycled.similarity = ft.similarity;
      recycled.missedFrames = ft.missed_frames;
      recycled.lastSeen = now;
      return recycled;
    }

    return {
      trackId: ft.track_id,
      x: new Animated.Value(ft.bbox[0]),
      y: new Animated.Value(ft.bbox[1]),
      w: new Animated.Value(ft.bbox[2]),
      h: new Animated.Value(ft.bbox[3]),
      opacity: new Animated.Value(0),
      userId: ft.user_id,
      name: ft.name,
      studentId: ft.student_id,
      similarity: ft.similarity,
      missedFrames: ft.missed_frames,
      lastSeen: now,
    };
  }
}
```

### Step 2: Verify TypeScript compiles

Run: `cd mobile && npx tsc --noEmit src/engines/TrackAnimationEngine.ts`
Expected: No errors.

### Step 3: Commit

```bash
git add mobile/src/engines/TrackAnimationEngine.ts
git commit -m "feat(mobile): add TrackAnimationEngine for spring-animated bbox tracking"
```

---

## Task 6: Refactor DetectionOverlay to Use TrackAnimationEngine

**Files:**
- Modify: `mobile/src/components/video/DetectionOverlay.tsx`

### Step 1: Refactor DetectionOverlay

Update `DetectionOverlay.tsx` to:
1. Accept `fused_tracks` messages instead of raw detections
2. Use `TrackAnimationEngine` for animation
3. Keep the existing `computeScale()` function
4. Render `Animated.View` boxes from engine output

Key changes:

```typescript
import { TrackAnimationEngine, FusedTrack, AnimatedTrack } from "../../engines/TrackAnimationEngine";

// Add new prop type for fused tracks
interface FusedDetectionOverlayProps {
  tracks: FusedTrack[];
  videoWidth: number;
  videoHeight: number;
  containerWidth: number;
  containerHeight: number;
  resizeMode?: "contain" | "cover";
}
```

Replace the `AnimatedDetectionBox` with a simpler component that reads from `AnimatedTrack`:

```typescript
const FusedBox = React.memo(({ track, scaleInfo }: {
  track: AnimatedTrack;
  scaleInfo: ScaleInfo;
}) => {
  const { scale, offsetX, offsetY } = scaleInfo;
  const isRecognized = track.userId != null;
  const color = isRecognized ? COLOR_RECOGNIZED : COLOR_UNKNOWN;
  const label = track.name
    ? `${track.name.split(" ")[0].substring(0, 10)} (${Math.round((track.similarity ?? 0) * 100)}%)`
    : "Unknown";

  // Derive animated screen positions from detection-space values
  const left = Animated.multiply(track.x, scale);
  const top = Animated.multiply(track.y, scale);
  const width = Animated.multiply(track.w, scale);
  const height = Animated.multiply(track.h, scale);

  // Note: Animated.add for offsets
  const screenLeft = Animated.add(left, offsetX);
  const screenTop = Animated.add(top, offsetY);

  return (
    <>
      <Animated.View
        style={{
          position: "absolute",
          left: screenLeft,
          top: screenTop,
          width: width,
          height: height,
          borderWidth: 2,
          borderColor: color,
          borderRadius: 3,
          opacity: track.opacity,
        }}
      />
      <Animated.View
        style={{
          position: "absolute",
          left: screenLeft,
          top: Animated.add(screenTop, -16),
          opacity: track.opacity,
        }}
      >
        <Text style={[styles.labelText, { color }]}>{label}</Text>
      </Animated.View>
    </>
  );
});
```

Use the engine in the main component via `useRef`:

```typescript
const engineRef = useRef(new TrackAnimationEngine());
const [animatedTracks, setAnimatedTracks] = useState<AnimatedTrack[]>([]);

useEffect(() => {
  const updated = engineRef.current.update(tracks);
  setAnimatedTracks(updated);
}, [tracks]);

// Cleanup on unmount
useEffect(() => {
  return () => engineRef.current.clear();
}, []);
```

### Step 2: Test on device

Run `pnpm android` or `pnpm ios`, connect to a live stream, verify:
- Boxes appear and track faces smoothly
- Green for recognized, amber for unknown
- Boxes fade in when appearing, fade out when disappearing
- No jank at 50+ boxes

### Step 3: Commit

```bash
git add mobile/src/components/video/DetectionOverlay.tsx
git commit -m "feat(mobile): refactor DetectionOverlay to use TrackAnimationEngine for spring animation"
```

---

## Task 7: Handle fused_tracks Message in Mobile WebSocket

**Files:**
- Modify: The screen/component that handles live stream WebSocket messages (likely `FacultyLiveAttendanceScreen.tsx` or similar)

### Step 1: Add fused_tracks message handler

Find the WebSocket `onmessage` handler for the live stream. Add handling for the new `fused_tracks` message type alongside the existing `detections` type:

```typescript
case "fused_tracks":
  const fusedTracks: FusedTrack[] = data.tracks.map((t: any) => ({
    track_id: t.track_id,
    bbox: t.bbox as [number, number, number, number],
    confidence: t.confidence,
    user_id: t.user_id,
    name: t.name,
    student_id: t.student_id,
    similarity: t.similarity,
    state: t.state,
    missed_frames: t.missed_frames,
  }));
  setDetectionWidth(data.frame_width);
  setDetectionHeight(data.frame_height);
  setFusedTracks(fusedTracks);
  break;
```

Pass `fusedTracks` to the refactored `DetectionOverlay` component.

### Step 2: Test end-to-end

Full pipeline test: RPi → VPS → Mobile. Verify bounding boxes track faces at 30 FPS.

### Step 3: Commit

```bash
git add <modified screen file>
git commit -m "feat(mobile): handle fused_tracks WebSocket message for live attendance"
```

---

## Task 8: Update Main Loop Caller on Edge (processor.py / run.py)

**Files:**
- Modify: The file that calls `detector.detect()` and `edge_ws.send_detections()` in the main loop (check `edge/app/processor.py` or `edge/run.py`)

### Step 1: Find and update the main detection loop

Locate where `detector.detect()` is called and the results are sent via `edge_ws.send_detections()`. Update to use the new tracked methods:

```python
# Replace:
#   faces = detector.detect(frame)
#   edge_ws.send_detections(det_list, w, h)
# With:
faces, tracked = detector.detect_and_track(frame)
edge_ws.send_tracked_detections(tracked, w, h, detector.frame_seq)
```

### Step 2: Test on RPi

SSH into RPi, run `python run.py`, verify logs show tracked detections being sent.

### Step 3: Commit

```bash
git add <modified file>
git commit -m "feat(edge): use detect_and_track in main loop for centroid-tracked detections"
```

---

## Task 9: Integration Testing & Cleanup

**Files:**
- All modified files from Tasks 1-8

### Step 1: Run backend tests

Run: `cd backend && pytest -v`
Expected: All tests pass including new `test_track_fusion.py`.

### Step 2: End-to-end test checklist

- [ ] RPi sends `edge_detections` with `track_id`, `centroid`, `velocity`, `frame_seq`
- [ ] VPS `TrackFusionService` creates fused tracks from edge detections
- [ ] VPS recognition identity merges into fused tracks
- [ ] Mobile receives `fused_tracks` at ~30 FPS
- [ ] Bounding boxes move smoothly following faces
- [ ] Boxes fade in/out gracefully
- [ ] Identity (name, green border) appears within 0.5-1s of face entering frame
- [ ] 50+ faces render without jank on mobile
- [ ] Boxes coast smoothly during brief WiFi drops

### Step 3: Final commit

```bash
git commit -m "test: verify layered bbox tracking end-to-end"
```

---

## Dependency Graph

```
Task 1 (CentroidTracker)
  └─→ Task 2 (Integrate into edge detection)
        └─→ Task 8 (Update main loop caller)

Task 3 (TrackFusionService + tests)
  └─→ Task 4 (Wire into edge relay + live stream)

Task 5 (TrackAnimationEngine)
  └─→ Task 6 (Refactor DetectionOverlay)
        └─→ Task 7 (Handle fused_tracks in mobile WS)

Task 9 (Integration testing) depends on all above
```

**Parallelizable:** Tasks 1-2, 3-4, and 5-7 can be worked on in parallel since they target different tiers (edge, backend, mobile).
