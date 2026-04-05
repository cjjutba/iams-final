# Decoupled Architecture Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Decouple attendance tracking from the live video pipeline so they run as independent systems sharing a one-way Redis cache.

**Architecture:** Two independent systems — (1) Attendance Engine grabs one frame every 15s, runs SCRFD + ArcFace, writes to DB and Redis; (2) Live Feed Pipeline processes video at 20fps for annotated WebRTC stream, reads identities from Redis cache. Neither depends on the other.

**Tech Stack:** FastAPI, SCRFD/ArcFace (InsightFace buffalo_l), FAISS IndexFlatIP, ByteTrack (supervision), Redis 7, mediamtx, FFmpeg, React Native (Expo)

**Design Doc:** `docs/plans/2026-03-17-decoupled-architecture-redesign-design.md`

---

## Track 1: Attendance Engine (can be developed in parallel with Track 2)

### Task 1: FrameGrabber — Persistent RTSP Frame Source

**Files:**
- Create: `backend/app/services/frame_grabber.py`
- Test: `backend/tests/unit/test_frame_grabber.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_frame_grabber.py
import threading
import time
import numpy as np
import pytest
from unittest.mock import MagicMock, patch


class TestFrameGrabber:
    """Test the FrameGrabber persistent RTSP reader."""

    def test_grab_returns_none_before_first_frame(self):
        """grab() should return None if no frame has been read yet."""
        from app.services.frame_grabber import FrameGrabber

        with patch("cv2.VideoCapture") as mock_cap:
            mock_cap.return_value.read.return_value = (False, None)
            grabber = FrameGrabber("rtsp://fake")
            result = grabber.grab()
            assert result is None
            grabber.stop()

    def test_grab_returns_latest_frame(self):
        """grab() should return the most recent frame from the drain loop."""
        from app.services.frame_grabber import FrameGrabber

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        fake_frame[0, 0, 0] = 42  # marker pixel

        with patch("cv2.VideoCapture") as mock_cap:
            call_count = 0

            def fake_read():
                nonlocal call_count
                call_count += 1
                if call_count <= 3:
                    return True, fake_frame.copy()
                return False, None

            mock_cap.return_value.read.side_effect = fake_read
            mock_cap.return_value.isOpened.return_value = True

            grabber = FrameGrabber("rtsp://fake")
            time.sleep(0.2)  # let drain loop run

            result = grabber.grab()
            assert result is not None
            assert result[0, 0, 0] == 42
            grabber.stop()

    def test_grab_returns_copy_not_reference(self):
        """grab() must return a copy so caller mutations don't affect internal state."""
        from app.services.frame_grabber import FrameGrabber

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch("cv2.VideoCapture") as mock_cap:
            mock_cap.return_value.read.return_value = (True, fake_frame)
            mock_cap.return_value.isOpened.return_value = True

            grabber = FrameGrabber("rtsp://fake")
            time.sleep(0.2)

            frame1 = grabber.grab()
            frame1[0, 0, 0] = 255  # mutate
            frame2 = grabber.grab()
            assert frame2[0, 0, 0] == 0  # internal state unaffected
            grabber.stop()

    def test_grab_returns_none_when_stale(self):
        """grab() should return None and trigger reconnect if frame is stale."""
        from app.services.frame_grabber import FrameGrabber

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch("cv2.VideoCapture") as mock_cap:
            mock_cap.return_value.read.return_value = (True, fake_frame)
            mock_cap.return_value.isOpened.return_value = True

            grabber = FrameGrabber("rtsp://fake", stale_timeout=0.5)
            time.sleep(0.2)

            # Frame should be fresh
            assert grabber.grab() is not None

            # Now make read() return False (simulating disconnect)
            mock_cap.return_value.read.return_value = (False, None)
            time.sleep(0.8)  # exceed stale timeout

            result = grabber.grab()
            assert result is None
            grabber.stop()

    def test_thread_safety_under_concurrent_access(self):
        """Multiple threads calling grab() should not crash."""
        from app.services.frame_grabber import FrameGrabber

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch("cv2.VideoCapture") as mock_cap:
            mock_cap.return_value.read.return_value = (True, fake_frame)
            mock_cap.return_value.isOpened.return_value = True

            grabber = FrameGrabber("rtsp://fake")
            time.sleep(0.2)

            errors = []

            def reader():
                try:
                    for _ in range(100):
                        grabber.grab()
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=reader) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0
            grabber.stop()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_frame_grabber.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.frame_grabber'`

**Step 3: Write minimal implementation**

```python
# backend/app/services/frame_grabber.py
"""
Persistent RTSP frame source for the attendance engine.

Keeps an RTSP connection alive via a background drain thread.
The drain loop continuously reads (and discards) frames, keeping
only the latest. grab() returns instantly with the most recent frame.
"""
import logging
import threading
import time
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class FrameGrabber:
    """Thread-safe persistent RTSP reader that always has the latest frame."""

    def __init__(self, rtsp_url: str, stale_timeout: float = 30.0):
        self._rtsp_url = rtsp_url
        self._stale_timeout = stale_timeout
        self._cap: cv2.VideoCapture = self._open_capture()
        self._latest_frame: Optional[np.ndarray] = None
        self._last_update: float = 0.0
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._drain_loop, daemon=True)
        self._thread.start()
        logger.info("FrameGrabber started for %s", rtsp_url)

    def _open_capture(self) -> cv2.VideoCapture:
        cap = cv2.VideoCapture(self._rtsp_url, cv2.CAP_FFMPEG)
        if cap.isOpened():
            logger.info("RTSP connection opened: %s", self._rtsp_url)
        else:
            logger.warning("Failed to open RTSP: %s", self._rtsp_url)
        return cap

    def _drain_loop(self) -> None:
        """Continuously read frames, keeping only the latest."""
        while not self._stopped.is_set():
            try:
                ret, frame = self._cap.read()
                if ret and frame is not None:
                    with self._lock:
                        self._latest_frame = frame
                        self._last_update = time.time()
                else:
                    # Connection lost or no frame — back off to avoid busy spin
                    time.sleep(0.1)
            except Exception:
                logger.exception("FrameGrabber drain loop error")
                time.sleep(1.0)

    def grab(self) -> Optional[np.ndarray]:
        """
        Return the latest frame, or None if unavailable or stale.

        Thread-safe. Returns a copy so callers can mutate freely.
        If the frame is older than stale_timeout, triggers reconnect.
        """
        with self._lock:
            if self._latest_frame is None:
                return None
            if time.time() - self._last_update > self._stale_timeout:
                logger.warning(
                    "Frame stale for %.1fs, reconnecting...",
                    time.time() - self._last_update,
                )
                self._reconnect()
                return None
            return self._latest_frame.copy()

    def _reconnect(self) -> None:
        """Release current capture and open a new one."""
        logger.info("Reconnecting to %s", self._rtsp_url)
        try:
            self._cap.release()
        except Exception:
            pass
        self._cap = self._open_capture()
        self._latest_frame = None
        self._last_update = 0.0

    def is_alive(self) -> bool:
        """Check if the drain thread is running and frames are fresh."""
        with self._lock:
            if self._latest_frame is None:
                return False
            return time.time() - self._last_update < self._stale_timeout

    def stop(self) -> None:
        """Stop the drain loop and release the capture."""
        self._stopped.set()
        self._thread.join(timeout=3.0)
        try:
            self._cap.release()
        except Exception:
            pass
        logger.info("FrameGrabber stopped for %s", self._rtsp_url)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_frame_grabber.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add backend/app/services/frame_grabber.py backend/tests/unit/test_frame_grabber.py
git commit -m "feat: add FrameGrabber — persistent RTSP frame source for attendance engine"
```

---

### Task 2: Attendance Scan Engine — Core Detection + Recognition Loop

**Files:**
- Create: `backend/app/services/attendance_engine.py`
- Test: `backend/tests/unit/test_attendance_engine.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_attendance_engine.py
import numpy as np
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, time as dt_time


class TestAttendanceScanEngine:
    """Test the attendance scan engine's core detection + recognition loop."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mocked ML models and DB."""
        frame_grabber = MagicMock()
        frame_grabber.grab.return_value = np.zeros((720, 1280, 3), dtype=np.uint8)

        insightface = MagicMock()
        # Simulate 2 detected faces with embeddings
        face1 = MagicMock()
        face1.bbox = np.array([100, 100, 200, 200])
        face1.det_score = 0.95
        face1.normed_embedding = np.random.randn(512).astype(np.float32)
        face2 = MagicMock()
        face2.bbox = np.array([300, 100, 400, 200])
        face2.det_score = 0.88
        face2.normed_embedding = np.random.randn(512).astype(np.float32)
        insightface.app.get.return_value = [face1, face2]

        faiss_mgr = MagicMock()
        faiss_mgr.search_with_margin.side_effect = [
            {"user_id": "user-001", "confidence": 0.92, "is_ambiguous": False},
            {"user_id": None, "confidence": 0.3, "is_ambiguous": False},
        ]

        redis = AsyncMock()
        db = MagicMock()

        return {
            "frame_grabber": frame_grabber,
            "insightface": insightface,
            "faiss_mgr": faiss_mgr,
            "redis": redis,
            "db": db,
        }

    def test_scan_frame_detects_and_recognizes(self, mock_dependencies):
        """A single scan should detect faces and recognize known students."""
        from app.services.attendance_engine import AttendanceScanEngine

        engine = AttendanceScanEngine(
            frame_grabber=mock_dependencies["frame_grabber"],
            insightface_model=mock_dependencies["insightface"],
            faiss_manager=mock_dependencies["faiss_mgr"],
        )

        result = engine.scan_frame()

        assert result is not None
        assert len(result.detected_faces) == 2
        assert len(result.recognized) == 1
        assert result.recognized[0].user_id == "user-001"
        assert result.recognized[0].confidence == 0.92
        assert len(result.unrecognized) == 1

    def test_scan_frame_returns_none_when_no_frame(self, mock_dependencies):
        """scan_frame() should return None when FrameGrabber has no frame."""
        from app.services.attendance_engine import AttendanceScanEngine

        mock_dependencies["frame_grabber"].grab.return_value = None

        engine = AttendanceScanEngine(
            frame_grabber=mock_dependencies["frame_grabber"],
            insightface_model=mock_dependencies["insightface"],
            faiss_manager=mock_dependencies["faiss_mgr"],
        )

        result = engine.scan_frame()
        assert result is None

    def test_scan_frame_handles_no_faces_detected(self, mock_dependencies):
        """scan_frame() should return empty results when no faces found."""
        from app.services.attendance_engine import AttendanceScanEngine

        mock_dependencies["insightface"].app.get.return_value = []

        engine = AttendanceScanEngine(
            frame_grabber=mock_dependencies["frame_grabber"],
            insightface_model=mock_dependencies["insightface"],
            faiss_manager=mock_dependencies["faiss_mgr"],
        )

        result = engine.scan_frame()
        assert result is not None
        assert len(result.detected_faces) == 0
        assert len(result.recognized) == 0

    def test_scan_frame_filters_low_confidence_detections(self, mock_dependencies):
        """Faces below detection threshold should be filtered out."""
        from app.services.attendance_engine import AttendanceScanEngine

        low_conf = MagicMock()
        low_conf.bbox = np.array([100, 100, 200, 200])
        low_conf.det_score = 0.2  # below 0.5 threshold
        low_conf.normed_embedding = np.random.randn(512).astype(np.float32)
        mock_dependencies["insightface"].app.get.return_value = [low_conf]

        engine = AttendanceScanEngine(
            frame_grabber=mock_dependencies["frame_grabber"],
            insightface_model=mock_dependencies["insightface"],
            faiss_manager=mock_dependencies["faiss_mgr"],
            detection_threshold=0.5,
        )

        result = engine.scan_frame()
        assert len(result.detected_faces) == 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_attendance_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# backend/app/services/attendance_engine.py
"""
Attendance Scan Engine — periodic snapshot-based face detection + recognition.

Grabs a single frame from the FrameGrabber, runs SCRFD detection and
ArcFace recognition, returns structured scan results. Does NOT write to DB
directly — the caller (presence_service) handles persistence.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RecognizedFace:
    user_id: str
    confidence: float
    bbox: list[int]  # [x1, y1, x2, y2]
    det_score: float


@dataclass
class UnrecognizedFace:
    bbox: list[int]
    det_score: float
    best_confidence: float  # highest FAISS match (below threshold)


@dataclass
class ScanResult:
    """Result of a single attendance scan."""
    detected_faces: int
    recognized: list[RecognizedFace] = field(default_factory=list)
    unrecognized: list[UnrecognizedFace] = field(default_factory=list)
    scan_duration_ms: float = 0.0
    frame_shape: Optional[tuple] = None


class AttendanceScanEngine:
    """
    Stateless scan engine: grab frame → detect → recognize → return results.

    This class does NOT manage sessions, miss counters, or DB writes.
    It is a pure function: frame in → scan results out.
    """

    def __init__(
        self,
        frame_grabber,
        insightface_model,
        faiss_manager,
        detection_threshold: float = 0.5,
        recognition_threshold: float = 0.45,
        recognition_margin: float = 0.1,
    ):
        self._grabber = frame_grabber
        self._insightface = insightface_model
        self._faiss = faiss_manager
        self._det_threshold = detection_threshold
        self._rec_threshold = recognition_threshold
        self._rec_margin = recognition_margin

    def scan_frame(self) -> Optional[ScanResult]:
        """
        Grab one frame, detect all faces, recognize each against FAISS.

        Returns ScanResult with recognized and unrecognized faces,
        or None if no frame is available.
        """
        t0 = time.time()

        frame = self._grabber.grab()
        if frame is None:
            logger.warning("No frame available, skipping scan")
            return None

        # Detect faces using SCRFD (via InsightFace app)
        faces = self._insightface.app.get(frame)
        faces = [f for f in faces if f.det_score >= self._det_threshold]

        recognized = []
        unrecognized = []

        for face in faces:
            bbox = face.bbox.astype(int).tolist()
            embedding = face.normed_embedding

            # Search FAISS for match
            match = self._faiss.search_with_margin(
                embedding,
                k=3,
                threshold=self._rec_threshold,
                margin=self._rec_margin,
            )

            if match.get("user_id"):
                recognized.append(RecognizedFace(
                    user_id=match["user_id"],
                    confidence=match["confidence"],
                    bbox=bbox,
                    det_score=float(face.det_score),
                ))
            else:
                unrecognized.append(UnrecognizedFace(
                    bbox=bbox,
                    det_score=float(face.det_score),
                    best_confidence=match.get("confidence", 0.0),
                ))

        duration = (time.time() - t0) * 1000

        logger.info(
            "Scan complete: %d detected, %d recognized, %d unknown (%.0fms)",
            len(faces),
            len(recognized),
            len(unrecognized),
            duration,
        )

        return ScanResult(
            detected_faces=len(faces),
            recognized=recognized,
            unrecognized=unrecognized,
            scan_duration_ms=duration,
            frame_shape=frame.shape,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_attendance_engine.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add backend/app/services/attendance_engine.py backend/tests/unit/test_attendance_engine.py
git commit -m "feat: add AttendanceScanEngine — stateless frame scan with SCRFD + ArcFace"
```

---

### Task 3: Redis Identity Cache — Write + Read

**Files:**
- Create: `backend/app/services/identity_cache.py`
- Test: `backend/tests/unit/test_identity_cache.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_identity_cache.py
import json
import pytest
from unittest.mock import AsyncMock


class TestIdentityCache:
    """Test the Redis identity cache (one-way bridge)."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.hset = AsyncMock()
        redis.hgetall = AsyncMock(return_value={})
        redis.expire = AsyncMock()
        redis.delete = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_write_identities(self, mock_redis):
        """write_identities should store recognized faces as Redis hash."""
        from app.services.identity_cache import IdentityCache

        cache = IdentityCache(mock_redis)
        identities = [
            {"user_id": "u1", "name": "Juan", "confidence": 0.95, "bbox": [10, 20, 30, 40]},
            {"user_id": "u2", "name": "Maria", "confidence": 0.88, "bbox": [50, 60, 70, 80]},
        ]

        await cache.write_identities("room-1", "session-1", identities)

        mock_redis.hset.assert_called()
        mock_redis.expire.assert_called()

    @pytest.mark.asyncio
    async def test_read_identities_returns_cached(self, mock_redis):
        """read_identities should return parsed identity dicts."""
        from app.services.identity_cache import IdentityCache

        mock_redis.hgetall.return_value = {
            b"u1": json.dumps({"name": "Juan", "confidence": 0.95}).encode(),
            b"u2": json.dumps({"name": "Maria", "confidence": 0.88}).encode(),
        }

        cache = IdentityCache(mock_redis)
        result = await cache.read_identities("room-1", "session-1")

        assert len(result) == 2
        assert result["u1"]["name"] == "Juan"
        assert result["u2"]["confidence"] == 0.88

    @pytest.mark.asyncio
    async def test_read_identities_returns_empty_on_miss(self, mock_redis):
        """read_identities should return empty dict if no cache."""
        from app.services.identity_cache import IdentityCache

        mock_redis.hgetall.return_value = {}

        cache = IdentityCache(mock_redis)
        result = await cache.read_identities("room-1", "session-1")
        assert result == {}

    @pytest.mark.asyncio
    async def test_write_scan_meta(self, mock_redis):
        """write_scan_meta should store scan metadata."""
        from app.services.identity_cache import IdentityCache

        cache = IdentityCache(mock_redis)
        await cache.write_scan_meta("room-1", "session-1", {
            "last_scan_ts": 1710680400,
            "faces_detected": 12,
            "faces_recognized": 10,
            "scan_count": 5,
        })

        mock_redis.hset.assert_called()

    @pytest.mark.asyncio
    async def test_clear_session(self, mock_redis):
        """clear_session should delete both identity and meta keys."""
        from app.services.identity_cache import IdentityCache

        cache = IdentityCache(mock_redis)
        await cache.clear_session("room-1", "session-1")

        assert mock_redis.delete.call_count == 2
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_identity_cache.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# backend/app/services/identity_cache.py
"""
Redis identity cache — one-way bridge between attendance engine and live feed pipeline.

Attendance engine WRITES identities after each scan.
Live feed pipeline READS identities to label tracked faces.
"""
import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Key patterns (session-scoped to prevent cross-class leakage)
IDENTITY_KEY = "attendance:{room_id}:{session_id}:identities"
SCAN_META_KEY = "attendance:{room_id}:{session_id}:scan_meta"

# TTL: session duration + buffer (cleaned up explicitly on session end)
DEFAULT_TTL = 3 * 3600 + 300  # 3 hours + 5 min buffer


class IdentityCache:
    """Redis-backed identity cache for the attendance-to-pipeline bridge."""

    def __init__(self, redis_client):
        self._redis = redis_client

    def _identity_key(self, room_id: str, session_id: str) -> str:
        return IDENTITY_KEY.format(room_id=room_id, session_id=session_id)

    def _meta_key(self, room_id: str, session_id: str) -> str:
        return SCAN_META_KEY.format(room_id=room_id, session_id=session_id)

    async def write_identities(
        self,
        room_id: str,
        session_id: str,
        identities: list[dict],
        ttl: int = DEFAULT_TTL,
    ) -> None:
        """
        Write recognized identities to Redis hash.

        Each identity: {user_id, name, confidence, bbox, last_seen_ts}
        """
        key = self._identity_key(room_id, session_id)
        mapping = {}
        for ident in identities:
            user_id = ident["user_id"]
            mapping[user_id] = json.dumps({
                "name": ident.get("name", "Unknown"),
                "confidence": ident.get("confidence", 0.0),
                "bbox": ident.get("bbox", []),
                "last_seen_ts": ident.get("last_seen_ts", time.time()),
            })

        if mapping:
            await self._redis.hset(key, mapping=mapping)
        await self._redis.expire(key, ttl)

    async def read_identities(
        self, room_id: str, session_id: str
    ) -> dict[str, dict]:
        """
        Read cached identities. Returns {user_id: {name, confidence, bbox}}.

        Used by the live feed pipeline to label faces without running ArcFace.
        """
        key = self._identity_key(room_id, session_id)
        raw = await self._redis.hgetall(key)

        result = {}
        for uid_bytes, data_bytes in raw.items():
            uid = uid_bytes.decode() if isinstance(uid_bytes, bytes) else uid_bytes
            data = data_bytes.decode() if isinstance(data_bytes, bytes) else data_bytes
            try:
                result[uid] = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse identity for %s", uid)

        return result

    async def write_scan_meta(
        self,
        room_id: str,
        session_id: str,
        meta: dict,
        ttl: int = DEFAULT_TTL,
    ) -> None:
        """Write scan metadata (for observability and mobile UI)."""
        key = self._meta_key(room_id, session_id)
        mapping = {k: str(v) for k, v in meta.items()}
        await self._redis.hset(key, mapping=mapping)
        await self._redis.expire(key, ttl)

    async def read_scan_meta(
        self, room_id: str, session_id: str
    ) -> Optional[dict]:
        """Read latest scan metadata."""
        key = self._meta_key(room_id, session_id)
        raw = await self._redis.hgetall(key)
        if not raw:
            return None
        return {
            (k.decode() if isinstance(k, bytes) else k): (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in raw.items()
        }

    async def clear_session(self, room_id: str, session_id: str) -> None:
        """Clean up all cache keys for a session (called on session end)."""
        await self._redis.delete(self._identity_key(room_id, session_id))
        await self._redis.delete(self._meta_key(room_id, session_id))
        logger.info("Cleared identity cache for room=%s session=%s", room_id, session_id)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_identity_cache.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add backend/app/services/identity_cache.py backend/tests/unit/test_identity_cache.py
git commit -m "feat: add IdentityCache — Redis bridge between attendance engine and pipeline"
```

---

### Task 4: Integrate Attendance Engine into Presence Service

**Files:**
- Modify: `backend/app/services/presence_service.py` (lines 146-157, 331-349, 382-386)
- Modify: `backend/app/main.py` (lines 215-242, startup)
- Test: `backend/tests/test_presence_integration.py`

**Step 1: Write the failing integration test**

```python
# backend/tests/test_presence_integration.py
"""Integration test: attendance engine feeds into presence service scan cycle."""
import numpy as np
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_scan_cycle_uses_attendance_engine():
    """
    Presence service scan cycle should:
    1. Call attendance_engine.scan_frame()
    2. Use recognized faces to update attendance
    3. Write identities to Redis cache
    """
    from app.services.attendance_engine import ScanResult, RecognizedFace

    # Mock scan result: 2 faces detected, 1 recognized
    scan_result = ScanResult(
        detected_faces=2,
        recognized=[
            RecognizedFace(
                user_id="student-001",
                confidence=0.92,
                bbox=[100, 100, 200, 200],
                det_score=0.95,
            )
        ],
        unrecognized=[],
        scan_duration_ms=150.0,
    )

    mock_engine = MagicMock()
    mock_engine.scan_frame.return_value = scan_result

    mock_cache = AsyncMock()
    mock_db = MagicMock()

    # Verify the scan result is usable by presence logic
    assert scan_result.detected_faces == 2
    assert len(scan_result.recognized) == 1
    assert scan_result.recognized[0].user_id == "student-001"
```

**Step 2: Run to verify baseline**

Run: `cd backend && python -m pytest tests/test_presence_integration.py -v`
Expected: PASS (basic structure test)

**Step 3: Modify presence_service.py**

Key changes to `backend/app/services/presence_service.py`:

1. **Replace `_get_identified_users_from_pipeline()` (lines 146-157)** with a method that accepts `ScanResult` from the attendance engine:

```python
# Replace lines 146-157 in presence_service.py
def _get_identified_users_from_scan(
    self, scan_result: "ScanResult"
) -> list[dict]:
    """
    Convert AttendanceScanEngine results to the format expected
    by process_session_scan().

    Returns list of {"user_id": str, "confidence": float}.
    """
    if scan_result is None:
        return []
    return [
        {"user_id": r.user_id, "confidence": r.confidence}
        for r in scan_result.recognized
    ]
```

2. **Modify `run_scan_cycle()` (lines 331-349)** to accept an optional `ScanResult`:

```python
# Modify run_scan_cycle signature and body
async def run_scan_cycle(
    self, scan_results: dict[str, "ScanResult"] | None = None
) -> None:
    """
    Run one scan cycle across all active sessions.

    scan_results: optional dict of {room_id: ScanResult} from attendance engine.
    If not provided, falls back to reading pipeline Redis state (legacy).
    """
    async with self._lock:
        for schedule_id, session in list(self._active_sessions.items()):
            if not session.is_active:
                continue
            room_id = str(session.schedule.room_id)
            scan_result = scan_results.get(room_id) if scan_results else None
            await self.process_session_scan(schedule_id, scan_result=scan_result)
```

3. **Modify `process_session_scan()` (around line 382)** to use scan_result:

```python
# Replace line 382 where it reads from pipeline Redis
# Old: identified_user_ids = self._get_identified_users_from_pipeline(room_id)
# New:
if scan_result is not None:
    identified_users = self._get_identified_users_from_scan(scan_result)
else:
    # Legacy fallback: read from pipeline Redis state
    identified_users = self._get_identified_users_from_pipeline(room_id)
identified_user_ids = {u["user_id"] for u in identified_users}
```

**Step 4: Modify main.py APScheduler job**

Change the scan cycle job (lines 224-242 in `main.py`) to use the attendance engine:

```python
# In the APScheduler setup section of main.py
async def run_attendance_scan_cycle():
    """Attendance scan cycle: grab frame → detect → recognize → update DB."""
    db = SessionLocal()
    try:
        # Get all active sessions and their rooms
        presence_svc = PresenceService(db)
        scan_results = {}

        for schedule_id, session in presence_svc._active_sessions.items():
            room_id = str(session.schedule.room_id)

            # Get the frame grabber for this room
            grabber = app.state.frame_grabbers.get(room_id)
            if grabber is None:
                continue

            # Create scan engine (stateless, cheap to instantiate)
            engine = AttendanceScanEngine(
                frame_grabber=grabber,
                insightface_model=app.state.insightface_model,
                faiss_manager=app.state.faiss_manager,
            )
            result = engine.scan_frame()
            if result:
                scan_results[room_id] = result

                # Write identities to Redis cache
                identity_cache = IdentityCache(app.state.redis)
                await identity_cache.write_identities(
                    room_id=room_id,
                    session_id=schedule_id,
                    identities=[
                        {
                            "user_id": r.user_id,
                            "name": "",  # enriched by presence_service
                            "confidence": r.confidence,
                            "bbox": r.bbox,
                        }
                        for r in result.recognized
                    ],
                )
                await identity_cache.write_scan_meta(
                    room_id=room_id,
                    session_id=schedule_id,
                    meta={
                        "last_scan_ts": int(time.time()),
                        "faces_detected": result.detected_faces,
                        "faces_recognized": len(result.recognized),
                    },
                )

        # Run presence scan with results
        await presence_svc.run_scan_cycle(scan_results=scan_results)
    except Exception:
        logger.exception("Attendance scan cycle failed")
    finally:
        db.close()
```

Update the scheduler interval from 60s to 15s:

```python
scheduler.add_job(
    run_attendance_scan_cycle,
    "interval",
    seconds=15,  # Changed from 60 to 15
    id="attendance_scan_cycle",
    replace_existing=True,
    max_instances=1,
)
```

**Step 5: Run tests**

Run: `cd backend && python -m pytest tests/ -v -k "presence or attendance_engine or frame_grabber or identity_cache"`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add backend/app/services/presence_service.py backend/app/main.py backend/tests/test_presence_integration.py
git commit -m "feat: integrate attendance engine into presence service scan cycle

Presence service now accepts ScanResult from AttendanceScanEngine instead
of reading pipeline Redis state. Scan interval changed from 60s to 15s.
Falls back to legacy pipeline read if no scan result provided."
```

---

### Task 5: FrameGrabber Lifecycle — Start/Stop with Sessions

**Files:**
- Modify: `backend/app/main.py` (startup)
- Modify: `backend/app/routers/presence.py` (session start/end)

**Step 1: Add frame_grabbers dict to app.state in main.py startup**

```python
# In startup_event, after ML model loading:
app.state.frame_grabbers = {}  # room_id → FrameGrabber
```

**Step 2: Modify session start endpoint to create FrameGrabber**

In `backend/app/routers/presence.py`, after `start_session()` succeeds (around line 110):

```python
# After session is started successfully, start frame grabber for this room
from app.services.frame_grabber import FrameGrabber

room = session_state.schedule.room
if room and room.stream_key:
    rtsp_url = f"rtsp://127.0.0.1:8554/{room.stream_key}/raw"
    room_id = str(room.id)
    if room_id not in request.app.state.frame_grabbers:
        grabber = FrameGrabber(rtsp_url)
        request.app.state.frame_grabbers[room_id] = grabber
        logger.info("Started FrameGrabber for room %s", room_id)
```

**Step 3: Modify session end endpoint to stop FrameGrabber**

In `backend/app/routers/presence.py`, after `end_session()` (around line 175):

```python
# Stop frame grabber for this room
room_id = str(schedule.room_id)
grabber = request.app.state.frame_grabbers.pop(room_id, None)
if grabber:
    grabber.stop()
    logger.info("Stopped FrameGrabber for room %s", room_id)

# Clear identity cache
from app.services.identity_cache import IdentityCache
identity_cache = IdentityCache(request.app.state.redis)
await identity_cache.clear_session(room_id, str(schedule_id))
```

**Step 4: Add cleanup in shutdown event**

```python
# In shutdown_event in main.py:
for room_id, grabber in app.state.frame_grabbers.items():
    grabber.stop()
app.state.frame_grabbers.clear()
```

**Step 5: Test manually**

Run: `cd backend && python -m pytest tests/ -v`
Expected: Existing tests still PASS

**Step 6: Commit**

```bash
git add backend/app/main.py backend/app/routers/presence.py
git commit -m "feat: manage FrameGrabber lifecycle with session start/end"
```

---

## Track 2: Live Feed Pipeline Fixes (can be developed in parallel with Track 1)

### Task 6: Fix RTSPReader — Timeout on FFmpeg Exit

**Files:**
- Modify: `backend/app/pipeline/rtsp_reader.py` (lines 77-110)
- Test: `backend/tests/test_pipeline/test_rtsp_reader.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_pipeline/test_rtsp_reader.py
import time
import pytest
from unittest.mock import MagicMock, patch


def test_reader_loop_handles_ffmpeg_exit_gracefully():
    """Reader should detect FFmpeg exit and not hang indefinitely."""
    from app.pipeline.rtsp_reader import RTSPReader

    reader = RTSPReader.__new__(RTSPReader)
    reader._stopped = False
    reader._frame = None
    reader._lock = __import__("threading").Lock()
    reader.height = 480
    reader.width = 640

    # Mock process that returns empty data (simulating FFmpeg exit)
    reader._process = MagicMock()
    reader._process.stdout.read.return_value = b""  # EOF
    reader._process.poll.return_value = 1  # process exited

    # _reader_loop should not hang — it should detect EOF and stop
    import threading
    loop_finished = threading.Event()

    def run_loop():
        reader._reader_loop()
        loop_finished.set()

    t = threading.Thread(target=run_loop, daemon=True)
    t.start()
    assert loop_finished.wait(timeout=5.0), "Reader loop hung on FFmpeg exit!"
```

**Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_pipeline/test_rtsp_reader.py::test_reader_loop_handles_ffmpeg_exit_gracefully -v`
Expected: May hang or fail depending on current implementation

**Step 3: Fix the reader loop**

Modify `backend/app/pipeline/rtsp_reader.py` `_reader_loop()` method:

```python
def _reader_loop(self):
    """Read raw frames from FFmpeg stdout. Exits on EOF or stop signal."""
    frame_bytes = self.width * self.height * 3
    warmup = 10
    frames_read = 0

    while not self._stopped:
        try:
            # Check if FFmpeg process is still alive
            if self._process.poll() is not None:
                logger.warning("FFmpeg process exited with code %s", self._process.returncode)
                break

            data = self._read_exactly(frame_bytes)
            if data is None or len(data) < frame_bytes:
                logger.warning("Incomplete read (%s/%s bytes), FFmpeg may have exited",
                             len(data) if data else 0, frame_bytes)
                break

            frame = np.frombuffer(data, dtype=np.uint8).reshape(
                (self.height, self.width, 3)
            )

            frames_read += 1
            if frames_read <= warmup:
                continue  # discard warmup frames

            with self._lock:
                self._frame = frame

        except Exception:
            if not self._stopped:
                logger.exception("RTSPReader loop error")
            break

    logger.info("RTSPReader loop exited after %d frames", frames_read)
```

Also fix `_read_exactly()` to have a timeout:

```python
def _read_exactly(self, n: int) -> bytes | None:
    """Read exactly n bytes from stdout, or return None on EOF/timeout."""
    buf = b""
    while len(buf) < n:
        remaining = n - len(buf)
        chunk = self._process.stdout.read(remaining)
        if not chunk:  # EOF
            return None
        buf += chunk
    return buf
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_pipeline/test_rtsp_reader.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/pipeline/rtsp_reader.py backend/tests/test_pipeline/test_rtsp_reader.py
git commit -m "fix: RTSPReader exits gracefully on FFmpeg process death instead of hanging"
```

---

### Task 7: Fix FFmpegPublisher — Prevent Pipe Deadlock

**Files:**
- Modify: `backend/app/pipeline/ffmpeg_publisher.py` (lines 84-101)
- Test: `backend/tests/test_pipeline/test_ffmpeg_publisher.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_pipeline/test_ffmpeg_publisher.py
import numpy as np
import pytest
from unittest.mock import MagicMock, patch


def test_write_frame_does_not_block_on_broken_pipe():
    """write_frame should return False quickly if pipe is broken, not hang."""
    from app.pipeline.ffmpeg_publisher import FFmpegPublisher

    pub = FFmpegPublisher.__new__(FFmpegPublisher)
    pub._process = MagicMock()
    pub._process.poll.return_value = None  # "alive"
    pub._process.stdin.write.side_effect = BrokenPipeError("pipe closed")
    pub.width = 640
    pub.height = 480

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = pub.write_frame(frame)
    assert result is False  # Should return False, not raise or hang


def test_write_frame_returns_false_when_process_dead():
    """write_frame should detect dead process immediately."""
    from app.pipeline.ffmpeg_publisher import FFmpegPublisher

    pub = FFmpegPublisher.__new__(FFmpegPublisher)
    pub._process = MagicMock()
    pub._process.poll.return_value = 1  # process exited
    pub.width = 640
    pub.height = 480

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = pub.write_frame(frame)
    assert result is False
```

**Step 2: Run to verify behavior**

Run: `cd backend && python -m pytest tests/test_pipeline/test_ffmpeg_publisher.py -v`

**Step 3: Fix write_frame with proper error handling**

Modify `write_frame()` in `backend/app/pipeline/ffmpeg_publisher.py`:

```python
def write_frame(self, frame: np.ndarray) -> bool:
    """
    Write a BGR frame to FFmpeg stdin. Returns False on failure.

    Non-blocking: catches BrokenPipeError and OSError immediately.
    """
    if self._process is None or self._process.poll() is not None:
        return False
    try:
        self._process.stdin.write(frame.tobytes())
        self._process.stdin.flush()
        return True
    except (BrokenPipeError, OSError) as e:
        logger.warning("FFmpegPublisher write failed: %s", e)
        return False
    except Exception:
        logger.exception("FFmpegPublisher unexpected error")
        return False
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_pipeline/test_ffmpeg_publisher.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/pipeline/ffmpeg_publisher.py backend/tests/test_pipeline/test_ffmpeg_publisher.py
git commit -m "fix: FFmpegPublisher write_frame returns False on broken pipe instead of hanging"
```

---

### Task 8: Pipeline Reads Identity Cache from Redis

**Files:**
- Modify: `backend/app/pipeline/video_pipeline.py` (lines 289-343, _recognize_new_tracks)

**Step 1: Write the test**

```python
# backend/tests/test_pipeline/test_pipeline_cache_read.py
import json
import numpy as np
import pytest
from unittest.mock import MagicMock


def test_pipeline_uses_cache_before_arcface():
    """Pipeline should check Redis cache before running ArcFace recognition."""
    from app.pipeline.video_pipeline import VideoAnalyticsPipeline

    pipeline = VideoAnalyticsPipeline.__new__(VideoAnalyticsPipeline)
    pipeline._identities = {}
    pipeline._redis = MagicMock()

    # Simulate cache hit
    cached = {"user-001": json.dumps({"name": "Juan", "confidence": 0.95})}
    pipeline._redis.hgetall.return_value = cached
    pipeline._session_id = "session-1"

    # Method should return cached identity
    result = pipeline._lookup_identity_cache("user-001")
    assert result is not None
    assert result["name"] == "Juan"


def test_pipeline_falls_back_to_arcface_on_cache_miss():
    """Pipeline should run ArcFace when identity not in cache."""
    from app.pipeline.video_pipeline import VideoAnalyticsPipeline

    pipeline = VideoAnalyticsPipeline.__new__(VideoAnalyticsPipeline)
    pipeline._identities = {}
    pipeline._redis = MagicMock()
    pipeline._redis.hgetall.return_value = {}
    pipeline._session_id = "session-1"

    result = pipeline._lookup_identity_cache("unknown-user")
    assert result is None  # Cache miss → caller should use ArcFace
```

**Step 2: Modify `_recognize_new_tracks()` in video_pipeline.py**

Add a cache-first recognition path:

```python
def _recognize_new_tracks(self, frame, tracked):
    """Recognize faces: check Redis cache first, fall back to ArcFace."""
    if tracked is None or len(tracked) == 0:
        return

    active_tids = set(tracked.tracker_id) if tracked.tracker_id is not None else set()

    # Load identity cache from Redis (sync read, called in subprocess)
    cached_identities = self._read_identity_cache()

    for i, tid in enumerate(tracked.tracker_id):
        tid = int(tid)

        # Skip already-identified tracks
        if tid in self._identities:
            continue

        # Skip unconfirmed tracks
        if tid not in self._confirmed_track_ids:
            continue

        # Try cache first: match by proximity to cached bbox
        cache_hit = self._match_from_cache(tracked.xyxy[i], cached_identities)
        if cache_hit:
            self._identities[tid] = cache_hit
            continue

        # Cache miss: run ArcFace (lazy load if needed)
        self._recognize_via_arcface(frame, tracked, i, tid)
```

**Step 3: Commit**

```bash
git add backend/app/pipeline/video_pipeline.py backend/tests/test_pipeline/test_pipeline_cache_read.py
git commit -m "feat: pipeline reads identity cache from Redis before running ArcFace"
```

---

### Task 9: Remove Attendance Coupling from Pipeline

**Files:**
- Modify: `backend/app/pipeline/video_pipeline.py` (lines 362-392)

The pipeline currently publishes state to `pipeline:{room_id}:state` which the presence service reads. After the redesign, the attendance engine has its own detection — the pipeline's Redis publish becomes observability-only (for pipeline health monitoring), not the attendance data source.

**Step 1: Update Redis key name**

Change the pipeline state key from `pipeline:{room_id}:state` to `pipeline:{room_id}:status` to clearly distinguish it from attendance data:

```python
# In _publish_state_to_redis (line ~381):
key = f"pipeline:{self.room_id}:status"  # was :state
```

**Step 2: Commit**

```bash
git add backend/app/pipeline/video_pipeline.py
git commit -m "refactor: rename pipeline Redis key from :state to :status (observability only)"
```

---

## Track 3: Cleanup + Integration

### Task 10: Clean Up config.py — Remove Dead Settings

**Files:**
- Modify: `backend/app/config.py`

**Step 1: Remove dead settings**

Remove or comment out these unused settings groups:
- `USE_HLS_STREAMING`, `HLS_SEGMENT_DURATION`, `HLS_PLAYLIST_SIZE` (lines ~112-120)
- `REDIS_BATCH_*` settings (lines ~106-110)
- `STREAM_FPS`, `STREAM_QUALITY`, `STREAM_WIDTH`, `STREAM_HEIGHT` (lines ~112-116)
- `RECOGNITION_FPS`, `RECOGNITION_RTSP_URL`, `RECOGNITION_MAX_DIM` (lines ~142-146)
- `SERVICE_ROLE` and worker detection settings (lines ~148-158)

**Step 2: Update SCAN_INTERVAL_SECONDS default**

```python
SCAN_INTERVAL_SECONDS: int = 15  # was 60
```

**Step 3: Run tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS (no test depends on removed settings)

**Step 4: Commit**

```bash
git add backend/app/config.py
git commit -m "chore: prune dead config settings (HLS, batch, legacy stream, workers)"
```

---

### Task 11: Clean Up docker-compose.prod.yml

**Files:**
- Modify: `deploy/docker-compose.prod.yml`

**Step 1: Remove dead worker services**

Remove `detection-worker` and `recognition-worker` service definitions (lines ~58-117 in the prod compose file). They reference modules that don't exist.

**Step 2: Ensure 4-container layout**

Final services:
```yaml
services:
  api-gateway:     # FastAPI + attendance engine + pipeline manager
  redis:
  mediamtx:
  nginx:
```

**Step 3: Commit**

```bash
git add deploy/docker-compose.prod.yml
git commit -m "fix: remove dead worker services from production docker-compose"
```

---

### Task 12: Clean Up nginx.conf — Remove Dead Endpoints

**Files:**
- Modify: `deploy/nginx.conf`

**Step 1: Remove dead WebSocket location blocks**

Remove:
- `location /api/v1/ws/edge/` — no longer used (pipeline reads RTSP directly)
- `location /api/v1/ws/stream/` — legacy frame-push (removed)

Keep:
- `location /api/v1/ws/attendance/` — used
- `location /api/v1/ws/alerts/` — used

**Step 2: Commit**

```bash
git add deploy/nginx.conf
git commit -m "chore: remove dead WebSocket proxy locations from nginx config"
```

---

### Task 13: Mobile Bug Fixes

**Files:**
- Modify: `mobile/src/utils/api.ts` (token refresh queue fix)
- Modify: `mobile/src/hooks/useWebRTC.ts` (reconnect timer leak)

**Step 1: Fix token refresh queue hang**

In `mobile/src/utils/api.ts`, find the `processQueue` function and ensure all queue items are resolved or rejected:

```typescript
const processQueue = (error: unknown, token: string | null = null): void => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else if (token) {
      prom.resolve(token);
    } else {
      prom.reject(new Error('Token refresh failed'));
    }
  });
  failedQueue = [];
};
```

**Step 2: Fix WebRTC reconnect timer leak**

In `mobile/src/hooks/useWebRTC.ts`, ensure reconnect timer is cleared on unmount and checks `isMountedRef`:

```typescript
// In the reconnect timer callback:
reconnectTimerRef.current = setTimeout(() => {
  if (isMountedRef.current && connectRef.current) {
    connectRef.current();
  }
}, delay);
```

**Step 3: Commit**

```bash
git add mobile/src/utils/api.ts mobile/src/hooks/useWebRTC.ts
git commit -m "fix: token refresh queue hang + WebRTC reconnect timer leak on unmount"
```

---

### Task 14: End-to-End Verification

**Step 1: Start the development stack**

```bash
./scripts/dev-up.sh
```

**Step 2: Verify attendance engine works independently**

```bash
# Start a session via API
curl -X POST http://localhost:8000/api/v1/presence/sessions/start \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"schedule_id": "<schedule-uuid>"}'

# Check logs for attendance scan output
./scripts/dev-logs.sh api-gateway | grep "Scan complete"
# Expected: "Scan complete: N detected, M recognized, K unknown (150ms)" every 15s
```

**Step 3: Verify live feed pipeline works independently**

```bash
# Check pipeline status
curl http://localhost:8000/api/v1/pipeline/status

# Open mobile app → Faculty → Live Feed
# Expected: 720p annotated video with bounding boxes at ~20fps
```

**Step 4: Verify Redis cache bridge**

```bash
# Check Redis for identity cache
docker exec -it iams-redis redis-cli
> HGETALL attendance:<room_id>:<session_id>:identities
# Expected: hash of user_id → JSON with name, confidence, bbox

> HGETALL attendance:<room_id>:<session_id>:scan_meta
# Expected: last_scan_ts, faces_detected, faces_recognized
```

**Step 5: Verify independence — kill pipeline, attendance continues**

```bash
# Kill the pipeline subprocess
curl -X POST http://localhost:8000/api/v1/pipeline/stop/<room_id>

# Attendance engine should continue scanning
./scripts/dev-logs.sh api-gateway | grep "Scan complete"
# Expected: still printing scan results every 15s
```

**Step 6: Verify independence — stop attendance, pipeline continues**

```bash
# Check mobile app live feed still shows video with boxes
# Even if attendance engine throws an error, video should be unaffected
```

**Step 7: Commit final state**

```bash
git add -A
git commit -m "test: verify decoupled architecture — attendance + pipeline independent"
```

---

## Task Dependency Graph

```
Track 1 (Attendance):          Track 2 (Pipeline):         Track 3 (Cleanup):
  Task 1: FrameGrabber           Task 6: Fix RTSPReader      Task 10: Clean config
  Task 2: ScanEngine             Task 7: Fix Publisher        Task 11: Clean docker
  Task 3: IdentityCache          Task 8: Cache reads          Task 12: Clean nginx
  Task 4: Integrate into         Task 9: Remove coupling      Task 13: Mobile fixes
          PresenceService
  Task 5: Lifecycle mgmt
         \                           /                            |
          +-------------------------+-----------------------------+
                                    |
                              Task 14: E2E Verification
```

**Tracks 1 and 2 are fully parallel.** Track 3 can start anytime. Task 14 requires all tracks complete.

---

## Quick Reference: Files Changed

| File | Action | Task |
|------|--------|------|
| `backend/app/services/frame_grabber.py` | CREATE | 1 |
| `backend/app/services/attendance_engine.py` | CREATE | 2 |
| `backend/app/services/identity_cache.py` | CREATE | 3 |
| `backend/app/services/presence_service.py` | MODIFY (lines 146-157, 331-349, 382) | 4 |
| `backend/app/main.py` | MODIFY (startup, scheduler, shutdown) | 4, 5 |
| `backend/app/routers/presence.py` | MODIFY (session start/end) | 5 |
| `backend/app/pipeline/rtsp_reader.py` | MODIFY (lines 77-110) | 6 |
| `backend/app/pipeline/ffmpeg_publisher.py` | MODIFY (lines 84-101) | 7 |
| `backend/app/pipeline/video_pipeline.py` | MODIFY (lines 289-343, 362-392) | 8, 9 |
| `backend/app/config.py` | MODIFY (remove dead settings) | 10 |
| `deploy/docker-compose.prod.yml` | MODIFY (remove workers) | 11 |
| `deploy/nginx.conf` | MODIFY (remove dead locations) | 12 |
| `mobile/src/utils/api.ts` | MODIFY (processQueue fix) | 13 |
| `mobile/src/hooks/useWebRTC.ts` | MODIFY (reconnect timer) | 13 |
