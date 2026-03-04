# Enterprise Live Feed Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the existing IAMS live feed pipeline to handle 50+ simultaneous students with ~1.5s latency, thread-safe name caching, exponential backoff reconnection, and polished mobile UI — making it enterprise-grade and thesis-defense ready.

**Architecture:** The system already has the right architecture (HLS video + WebSocket metadata overlay). This plan tightens 7 specific bottlenecks without changing the design. Video and detection metadata travel independently; the overlay stays synced because both streams operate at the same latency.

**Tech Stack:** Python 3.11, FastAPI, FFmpeg (HLS), OpenCV, FaceNet+FAISS, React Native, expo-video, TypeScript

---

## Task 1: Raise recognition batch limit and tuning settings

**Files:**
- Modify: `backend/app/config.py`

**Context:** `RECOGNITION_MAX_BATCH_SIZE` defaults to 20. With 50+ students in frame, faces beyond index 20 are silently dropped. `RECOGNITION_FPS` is 8.0 — raising to 10.0 gives more responsive detection. HLS segment duration is 1s at playlist size 2 (3-6s latency) — cutting to 0.5s at size 3 targets 1.5-2.5s.

**Step 1: Update default values in config**

In `backend/app/config.py`, change these four defaults:

```python
# Face Recognition — change from 20 to 50
RECOGNITION_MAX_BATCH_SIZE: int = 50

# Recognition loop — change from 8.0 to 10.0
RECOGNITION_FPS: float = 10.0

# HLS — change from 1 to 0.5 and 2 to 3
HLS_SEGMENT_DURATION: int = 1   # → change type to float, value to 0.5
HLS_PLAYLIST_SIZE: int = 2      # → change to 3
```

**IMPORTANT:** `HLS_SEGMENT_DURATION` must become `float` because `0.5` is not an int. Change its type annotation to `float`:
```python
HLS_SEGMENT_DURATION: float = 0.5
HLS_PLAYLIST_SIZE: int = 3
```

**Step 2: Write a test verifying the new defaults**

Create `backend/tests/unit/test_config_defaults.py`:

```python
"""Verify production-tuned config defaults."""
import os
import importlib


def test_recognition_batch_size_default():
    """Batch size must be ≥ 50 to handle a full classroom."""
    from app.config import settings
    assert settings.RECOGNITION_MAX_BATCH_SIZE >= 50


def test_recognition_fps_default():
    """At least 10 FPS for responsive detection metadata."""
    from app.config import settings
    assert settings.RECOGNITION_FPS >= 10.0


def test_hls_segment_duration_is_low_latency():
    """≤ 1.0s segments for low-latency HLS."""
    from app.config import settings
    assert settings.HLS_SEGMENT_DURATION <= 1.0


def test_hls_playlist_window():
    """At least 3 segments in playlist for smooth playback."""
    from app.config import settings
    assert settings.HLS_PLAYLIST_SIZE >= 3
```

**Step 3: Run the test (should fail — old defaults)**

```bash
cd backend && pytest tests/unit/test_config_defaults.py -v
```
Expected: FAIL — `assert 20 >= 50` or similar.

**Step 4: Apply the config changes, then run again**

Edit `backend/app/config.py` as described above.

```bash
cd backend && pytest tests/unit/test_config_defaults.py -v
```
Expected: 4 PASSED.

**Step 5: Run full test suite to catch regressions**

```bash
cd backend && pytest --tb=short -q 2>&1 | tail -20
```
Expected: same pass/fail count as before (no new failures).

**Step 6: Commit**

```bash
git add backend/app/config.py backend/tests/unit/test_config_defaults.py
git commit -m "feat(config): raise recognition batch to 50, HLS to 0.5s segments, 10 FPS"
```

---

## Task 2: HLS fMP4 low-latency segments

**Files:**
- Modify: `backend/app/services/hls_service.py`

**Context:** The current FFmpeg command uses MPEG-TS segments (`.ts`). Switching to fMP4 (`.m4s`) gives better compatibility with modern iOS/Android HLS decoders, reduces segment overhead, and enables future LL-HLS. The init segment (`init.mp4`) is needed once per stream. The existing `get_segment` endpoint already serves any file by name — it just needs to allow `init.mp4`.

**Step 1: Write a test for FFmpeg command structure**

Create `backend/tests/unit/test_hls_service.py`:

```python
"""
Unit tests for HLS service FFmpeg command construction.

These tests verify the FFmpeg command list that hls_service builds
without actually spawning FFmpeg. They patch subprocess.Popen so
no external process is started.
"""
import os
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def hls(tmp_path, monkeypatch):
    """Return a fresh HLSService with temp segment dir."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    from app.services.hls_service import HLSService
    svc = HLSService()
    svc._segment_base = str(tmp_path)
    return svc


def _capture_cmd(hls_svc, room_id="room1", rtsp_url="rtsp://cam/stream"):
    """Run start_stream with mocked Popen; return the captured cmd list."""
    import asyncio

    captured = {}

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # process still alive

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return mock_proc

    with patch("subprocess.Popen", side_effect=fake_popen):
        with patch.object(hls_svc, "_wait_for_playlist", return_value=True):
            asyncio.get_event_loop().run_until_complete(
                hls_svc.start_stream(room_id, rtsp_url, "viewer1")
            )

    return captured.get("cmd", [])


def test_ffmpeg_uses_copy_codec(hls):
    cmd = _capture_cmd(hls)
    assert "-c:v" in cmd
    idx = cmd.index("-c:v")
    assert cmd[idx + 1] == "copy", "Must remux without transcoding"


def test_ffmpeg_uses_fmp4_segments(hls):
    cmd = _capture_cmd(hls)
    assert "-hls_segment_type" in cmd
    idx = cmd.index("-hls_segment_type")
    assert cmd[idx + 1] == "fmp4"


def test_ffmpeg_has_init_filename(hls):
    cmd = _capture_cmd(hls)
    assert "-hls_fmp4_init_filename" in cmd
    idx = cmd.index("-hls_fmp4_init_filename")
    assert cmd[idx + 1] == "init.mp4"


def test_ffmpeg_low_latency_flags(hls):
    cmd = _capture_cmd(hls)
    # Must include nobuffer
    assert any("nobuffer" in str(f) for f in cmd)


def test_segment_duration_matches_config(hls):
    from app.config import settings
    cmd = _capture_cmd(hls)
    assert "-hls_time" in cmd
    idx = cmd.index("-hls_time")
    assert cmd[idx + 1] == str(settings.HLS_SEGMENT_DURATION)


def test_playlist_size_matches_config(hls):
    from app.config import settings
    cmd = _capture_cmd(hls)
    assert "-hls_list_size" in cmd
    idx = cmd.index("-hls_list_size")
    assert cmd[idx + 1] == str(settings.HLS_PLAYLIST_SIZE)
```

**Step 2: Run the tests (expect failures)**

```bash
cd backend && pytest tests/unit/test_hls_service.py -v
```
Expected: `test_ffmpeg_uses_fmp4_segments` and `test_ffmpeg_has_init_filename` FAIL.

**Step 3: Update `hls_service.py` FFmpeg command**

In `backend/app/services/hls_service.py`, find the `cmd = [...]` block inside `start_stream` and update it:

```python
cmd = [
    ffmpeg_path,
    # Low-latency input flags
    "-fflags", "nobuffer+genpts",
    "-flags", "low_delay",
    "-probesize", "512000",
    "-analyzeduration", "500000",
    "-rtsp_transport", "tcp",
    "-i", rtsp_url,
    "-c:v", "copy",          # Remux without transcoding; zero CPU overhead
    "-an",                    # No audio
    "-f", "hls",
    "-hls_time", str(settings.HLS_SEGMENT_DURATION),
    "-hls_list_size", str(settings.HLS_PLAYLIST_SIZE),
    "-hls_flags", "delete_segments+append_list+split_by_time+omit_endlist",
    "-hls_segment_type", "fmp4",           # fMP4 segments (better decoder compat)
    "-hls_fmp4_init_filename", "init.mp4", # Init segment for fMP4
    "-hls_segment_filename", segment_pattern,
    playlist_path,
]
```

Also update the `segment_pattern` line (which currently uses `.ts`). Change:
```python
segment_pattern = os.path.join(segment_dir, "seg_%05d.ts")
```
to:
```python
segment_pattern = os.path.join(segment_dir, "seg_%05d.m4s")
```

**Step 4: Update `_cleanup_segments` to also clean `.m4s` and `init.mp4`**

In `_cleanup_segments`, add `"*.m4s"` and `"init.mp4"` to the pattern list:

```python
for pattern in ("*.m3u8", "*.ts", "*.m4s", "init.mp4"):
    for f in glob.glob(os.path.join(segment_dir, pattern)):
        os.remove(f)
```

**Step 5: Update `get_segment` router to allow `init.mp4`**

In `backend/app/routers/hls.py`, the `get_segment` endpoint already rejects paths with `..` or `/`. The `media_type` check only handles `.ts` and `.m3u8`. Add `.m4s` and `.mp4`:

```python
if filename.endswith(".ts") or filename.endswith(".m4s"):
    media_type = "video/mp2t"
elif filename.endswith(".mp4"):
    media_type = "video/mp4"
elif filename.endswith(".m3u8"):
    media_type = "application/vnd.apple.mpegurl"
else:
    media_type = "application/octet-stream"
```

**Step 6: Run tests**

```bash
cd backend && pytest tests/unit/test_hls_service.py -v
```
Expected: all 6 PASS.

**Step 7: Full suite**

```bash
cd backend && pytest --tb=short -q 2>&1 | tail -20
```

**Step 8: Commit**

```bash
git add backend/app/services/hls_service.py backend/app/routers/hls.py backend/tests/unit/test_hls_service.py
git commit -m "feat(hls): fMP4 segments, 0.5s duration, cleanup .m4s files"
```

---

## Task 3: Exponential backoff for RTSP reconnection

**Files:**
- Modify: `backend/app/services/recognition_service.py`

**Context:** Current `_reconnect` sleeps a fixed `2.0` seconds between attempts. Under flaky networks this floods reconnect attempts. Exponential backoff (2→4→8→16→30s max) is the industry standard. The `RecognitionState` dataclass needs a `backoff` field to track current delay. Successful reconnection resets it.

**Step 1: Write failing tests for backoff**

Create `backend/tests/unit/test_recognition_backoff.py`:

```python
"""
Tests for recognition service RTSP reconnection backoff.
We verify the backoff math without touching real RTSP streams.
"""
import time
import threading
import pytest
from unittest.mock import MagicMock, patch
from app.services.recognition_service import RecognitionService, RecognitionState


def make_state(room_id="test-room"):
    return RecognitionState(room_id=room_id, rtsp_url="rtsp://fake/stream")


def test_initial_backoff_is_zero():
    """State starts with no backoff."""
    state = make_state()
    assert state.reconnect_backoff == 0.0


def test_reconnect_increases_backoff():
    """Each failed reconnect doubles the delay (up to max)."""
    svc = RecognitionService.__new__(RecognitionService)
    svc._lock = threading.Lock()

    state = make_state()
    state.reconnect_backoff = 0.0

    # Simulate failed open_capture
    with patch.object(svc, "_open_capture", return_value=False):
        with patch("time.sleep"):  # don't actually sleep
            svc._reconnect(state)
            first_backoff = state.reconnect_backoff

    assert first_backoff == 2.0, f"Expected 2.0, got {first_backoff}"


def test_reconnect_backoff_doubles():
    """Second failure doubles backoff to 4.0."""
    svc = RecognitionService.__new__(RecognitionService)
    svc._lock = threading.Lock()

    state = make_state()
    state.reconnect_backoff = 2.0

    with patch.object(svc, "_open_capture", return_value=False):
        with patch("time.sleep"):
            svc._reconnect(state)

    assert state.reconnect_backoff == 4.0


def test_reconnect_backoff_caps_at_30():
    """Backoff does not exceed 30 seconds."""
    svc = RecognitionService.__new__(RecognitionService)
    svc._lock = threading.Lock()

    state = make_state()
    state.reconnect_backoff = 16.0

    with patch.object(svc, "_open_capture", return_value=False):
        with patch("time.sleep"):
            svc._reconnect(state)

    assert state.reconnect_backoff == 30.0, f"Got {state.reconnect_backoff}"


def test_successful_reconnect_resets_backoff():
    """Successful connection resets backoff to 0."""
    svc = RecognitionService.__new__(RecognitionService)
    svc._lock = threading.Lock()

    state = make_state()
    state.reconnect_backoff = 8.0

    with patch.object(svc, "_open_capture", return_value=True):
        with patch("time.sleep"):
            result = svc._reconnect(state)

    assert result is True
    assert state.reconnect_backoff == 0.0


def test_sleep_duration_matches_backoff():
    """time.sleep is called with the current backoff value."""
    svc = RecognitionService.__new__(RecognitionService)
    svc._lock = threading.Lock()

    state = make_state()
    state.reconnect_backoff = 0.0

    slept = []
    with patch.object(svc, "_open_capture", return_value=False):
        with patch("time.sleep", side_effect=lambda d: slept.append(d)):
            svc._reconnect(state)

    # First reconnect: initial sleep before trying (2s as first backoff)
    assert any(d >= 2.0 for d in slept), f"Expected sleep >= 2s, got {slept}"
```

**Step 2: Run tests (expect AttributeError or AssertionError)**

```bash
cd backend && pytest tests/unit/test_recognition_backoff.py -v
```
Expected: FAIL — `RecognitionState` has no `reconnect_backoff` field.

**Step 3: Update `RecognitionState` dataclass**

In `backend/app/services/recognition_service.py`, add the field to `RecognitionState`:

```python
@dataclass
class RecognitionState:
    """Mutable state for a single room's recognition pipeline."""
    room_id: str
    rtsp_url: str
    capture: Optional[cv2.VideoCapture] = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    viewers: Set[str] = field(default_factory=set)
    last_detections: List[Detection] = field(default_factory=list)
    last_detections_dicts: List[dict] = field(default_factory=list)
    last_timestamp: float = 0.0
    update_seq: int = 0
    frame_width: int = 0
    frame_height: int = 0
    reconnect_backoff: float = 0.0    # ← ADD THIS
```

**Step 4: Rewrite `_reconnect` with exponential backoff**

Replace the current `_reconnect` method:

```python
_BACKOFF_BASE: float = 2.0
_BACKOFF_MAX: float = 30.0

def _reconnect(self, state: RecognitionState) -> bool:
    """Attempt to reconnect using exponential backoff."""
    if state.capture is not None:
        try:
            state.capture.release()
        except Exception:
            pass
        state.capture = None

    # Compute sleep duration before this attempt
    delay = state.reconnect_backoff if state.reconnect_backoff > 0 else self._BACKOFF_BASE
    delay = min(delay, self._BACKOFF_MAX)
    logger.warning(
        f"Recognition: reconnecting for room {state.room_id} "
        f"(backoff={delay:.1f}s)"
    )
    time.sleep(delay)

    success = self._open_capture(state)
    if success:
        state.reconnect_backoff = 0.0
        logger.info(f"Recognition: reconnected for room {state.room_id}")
    else:
        # Double backoff for next attempt, capped at max
        next_backoff = delay * 2.0 if state.reconnect_backoff > 0 else delay
        state.reconnect_backoff = min(next_backoff, self._BACKOFF_MAX)
    return success
```

**Step 5: Run tests**

```bash
cd backend && pytest tests/unit/test_recognition_backoff.py -v
```
Expected: 5 PASSED.

**Step 6: Full suite**

```bash
cd backend && pytest --tb=short -q 2>&1 | tail -20
```

**Step 7: Commit**

```bash
git add backend/app/services/recognition_service.py backend/tests/unit/test_recognition_backoff.py
git commit -m "feat(recognition): exponential backoff RTSP reconnection (2s→30s max)"
```

---

## Task 4: Thread-safe name cache with TTL

**Files:**
- Modify: `backend/app/routers/live_stream.py`

**Context:** `_name_cache` is a module-level plain `dict`. Multiple coroutines from different rooms can write to it concurrently, causing race conditions. We replace it with a `NameCache` class that uses `threading.Lock` and 5-minute TTL per entry. This ensures stale names (e.g., student ID change) are refreshed automatically.

**Step 1: Write failing tests**

Create `backend/tests/unit/test_name_cache.py`:

```python
"""
Tests for the thread-safe NameCache used in live_stream.py.

Verifies: set/get, TTL expiry, thread safety under concurrent writes.
"""
import time
import threading
import pytest


# We import the class directly once it exists
def get_cache_class():
    from app.routers.live_stream import NameCache
    return NameCache


def test_cache_stores_and_retrieves():
    NameCache = get_cache_class()
    cache = NameCache(ttl_seconds=60)
    cache.set("user-1", "Alice Santos", "2023-0001")
    name, sid = cache.get("user-1")
    assert name == "Alice Santos"
    assert sid == "2023-0001"


def test_cache_returns_none_for_missing_key():
    NameCache = get_cache_class()
    cache = NameCache(ttl_seconds=60)
    assert cache.get("nonexistent") is None


def test_cache_expires_after_ttl(monkeypatch):
    """Entries should expire after TTL seconds."""
    NameCache = get_cache_class()
    cache = NameCache(ttl_seconds=1)
    cache.set("user-2", "Bob Reyes", "2023-0002")

    # Manually advance the timestamp stored in cache
    with cache._lock:
        # Set stored time to 2 seconds ago
        cache._store["user-2"] = (
            cache._store["user-2"][0],  # (name, sid)
            time.monotonic() - 2,       # expired timestamp
        )

    assert cache.get("user-2") is None, "Expired entry should return None"


def test_cache_is_thread_safe():
    """Concurrent writes must not corrupt the cache."""
    NameCache = get_cache_class()
    cache = NameCache(ttl_seconds=300)
    errors = []

    def writer(uid, name):
        try:
            for _ in range(100):
                cache.set(uid, name, f"id-{uid}")
                cache.get(uid)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(f"u{i}", f"Student {i}")) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread safety errors: {errors}"


def test_cache_overwrite_refreshes_ttl(monkeypatch):
    """Re-setting an entry resets its TTL."""
    NameCache = get_cache_class()
    cache = NameCache(ttl_seconds=1)
    cache.set("user-3", "Carol Tan", "2023-0003")

    # Expire it
    with cache._lock:
        cache._store["user-3"] = (
            cache._store["user-3"][0],
            time.monotonic() - 2,
        )

    # Re-set with fresh TTL
    cache.set("user-3", "Carol Tan Updated", "2023-0003")
    result = cache.get("user-3")
    assert result is not None
    assert result[0] == "Carol Tan Updated"
```

**Step 2: Run tests (expect ImportError)**

```bash
cd backend && pytest tests/unit/test_name_cache.py -v
```
Expected: FAIL — `ImportError: cannot import name 'NameCache'`.

**Step 3: Add `NameCache` class to `live_stream.py` and wire it in**

At the top of `backend/app/routers/live_stream.py`, replace:

```python
# Cache resolved student names so we don't hit the DB on every frame.
_name_cache: Dict[str, tuple] = {}
```

with:

```python
import threading as _threading


class NameCache:
    """Thread-safe student name cache with per-entry TTL."""

    def __init__(self, ttl_seconds: float = 300.0):
        self._lock = _threading.Lock()
        self._store: Dict[str, tuple] = {}  # uid → ((name, student_id), inserted_at)
        self._ttl = ttl_seconds

    def get(self, user_id: str):
        """Return (name, student_id) or None if missing/expired."""
        import time
        with self._lock:
            entry = self._store.get(user_id)
        if entry is None:
            return None
        value, inserted_at = entry
        if time.monotonic() - inserted_at > self._ttl:
            with self._lock:
                self._store.pop(user_id, None)
            return None
        return value

    def set(self, user_id: str, name: str, student_id: str) -> None:
        import time
        with self._lock:
            self._store[user_id] = ((name, student_id), time.monotonic())


# 5-minute TTL — refresh if student name changes in DB
_name_cache = NameCache(ttl_seconds=300)
```

**Step 4: Update `_enrich_and_cache` to use the new API**

Replace the function body to use `_name_cache.get()` and `_name_cache.set()`:

```python
def _enrich_and_cache(detections_dicts: list, detections_objects, db_session_factory) -> list:
    """Enrich detection dicts with cached student names (thread-safe, TTL-aware)."""
    needs_lookup = [
        d for d in detections_dicts
        if d.get("user_id") and not d.get("name") and _name_cache.get(d["user_id"]) is None
    ]

    if needs_lookup:
        db = db_session_factory()
        try:
            from app.services.recognition_service import recognition_service
            recognition_service.enrich_detections(detections_objects, db)
            for det in detections_objects:
                if det.user_id and det.name:
                    _name_cache.set(det.user_id, det.name, det.student_id or "")
            detections_dicts = [d.to_dict() for d in detections_objects]
        finally:
            db.close()

    # Apply cache to dicts missing names
    for d in detections_dicts:
        uid = d.get("user_id")
        if uid and not d.get("name"):
            cached = _name_cache.get(uid)
            if cached:
                d["name"], d["student_id"] = cached

    return detections_dicts
```

**Step 5: Run cache tests**

```bash
cd backend && pytest tests/unit/test_name_cache.py -v
```
Expected: 5 PASSED.

**Step 6: Full suite**

```bash
cd backend && pytest --tb=short -q 2>&1 | tail -20
```

**Step 7: Raise poll interval from 125ms to 100ms (10Hz metadata push)**

In `_hls_mode()`, change:
```python
poll_interval = 0.125  # 125ms = 8Hz
```
to:
```python
poll_interval = 0.100  # 100ms = 10Hz, matching RECOGNITION_FPS
```

**Step 8: Commit**

```bash
git add backend/app/routers/live_stream.py backend/tests/unit/test_name_cache.py
git commit -m "feat(stream): thread-safe name cache with 5min TTL, 10Hz metadata push"
```

---

## Task 5: Mobile — exponential backoff WebSocket reconnection

**Files:**
- Modify: `mobile/src/hooks/useDetectionWebSocket.ts`

**Context:** The mobile hook reconnects after a fixed 3-second delay. Under poor connectivity this means 3s between every retry regardless of how many times it's failed, which can hammer the server. Exponential backoff (1→2→4→8→16→30s max, reset on success) is the production standard.

**Step 1: Add backoff logic to `useDetectionWebSocket.ts`**

Add two refs inside the hook (after existing refs):

```typescript
const reconnectAttemptRef = useRef(0);
const MAX_RECONNECT_DELAY = 30_000; // ms
const BASE_RECONNECT_DELAY = 1_000; // ms
```

Replace the reconnect section inside `ws.onclose`:

```typescript
ws.onclose = () => {
  if (pingIntervalRef.current) {
    clearInterval(pingIntervalRef.current);
    pingIntervalRef.current = null;
  }
  if (!isMountedRef.current) return;
  setIsConnected(false);
  setIsConnecting(false);

  if (hasErrorRef.current) return;

  // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s max
  const attempt = reconnectAttemptRef.current;
  const delay = Math.min(BASE_RECONNECT_DELAY * Math.pow(2, attempt), MAX_RECONNECT_DELAY);
  reconnectAttemptRef.current = attempt + 1;

  reconnectTimeoutRef.current = setTimeout(() => {
    if (isMountedRef.current) {
      connectWebSocket();
    }
  }, delay);
};
```

Reset the attempt counter on successful connection inside `ws.onopen`:

```typescript
ws.onopen = () => {
  if (!isMountedRef.current) return;
  reconnectAttemptRef.current = 0;  // ← ADD THIS LINE
  setIsConnected(true);
  setIsConnecting(false);
  setConnectionError(null);
  // ... rest of existing onopen code
```

Also reset in the `reconnect` export function (it's `connectWebSocket`). Add before calling it:

```typescript
reconnect: () => {
  reconnectAttemptRef.current = 0;
  connectWebSocket();
},
```

Update the return object to pass the reset version:

```typescript
return {
  detections,
  isConnected,
  isConnecting,
  hlsUrl,
  studentMap,
  connectionError,
  reconnect: () => {
    reconnectAttemptRef.current = 0;
    connectWebSocket();
  },
  detectionWidth,
  detectionHeight,
};
```

**Step 2: Test by inspection (TypeScript — no unit test runner)**

Run TypeScript type-check to catch any type errors:

```bash
cd mobile && npx tsc --noEmit 2>&1 | grep useDetectionWebSocket
```
Expected: No errors from `useDetectionWebSocket.ts`.

**Step 3: Commit**

```bash
git add mobile/src/hooks/useDetectionWebSocket.ts
git commit -m "feat(mobile): exponential backoff WebSocket reconnection (1s→30s max)"
```

---

## Task 6: Mobile — enterprise-grade detection overlay

**Files:**
- Modify: `mobile/src/components/video/DetectionOverlay.tsx`

**Context:** Current overlay has thin borders (2px), small labels with dark text on colored background, and recreates `DetectionBox` animations on every update. Production CCTV overlays use: thick neon borders (3px), white text on semi-transparent dark backgrounds, stable box identity by `user_id`, and an "unknown" face indicator separate from recognized faces.

**Step 1: Rewrite `DetectionOverlay.tsx`**

Replace the entire file with this enterprise-grade version:

```typescript
/**
 * DetectionOverlay — Enterprise-grade face detection overlay.
 *
 * Renders bounding boxes over the HLS video player using absolute
 * positioned Views. Scales detection coordinates from the backend's
 * processing resolution to the on-screen container, accounting for
 * letterboxing (contentFit="contain").
 *
 * Design choices (CCTV industry standard):
 * - Recognized faces: 3px green border, dark label, confidence %
 * - Unknown faces:    3px amber border, "Unknown" label
 * - Stable keys by user_id → no animation flicker on update
 * - Smooth fade-in on first appearance only
 */

import React, { useEffect, useRef, useMemo } from 'react';
import { Animated, View, Text, StyleSheet } from 'react-native';

// ---------------------------------------------------------------------------
// Types (re-exported for consumers)
// ---------------------------------------------------------------------------

export interface DetectionBBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DetectionItem {
  bbox: DetectionBBox;
  confidence: number;
  user_id: string | null;
  student_id: string | null;
  name: string | null;
  similarity: number | null;
}

interface DetectionOverlayProps {
  detections: DetectionItem[];
  /** Frame width backend used for detection. */
  videoWidth: number;
  /** Frame height backend used for detection. */
  videoHeight: number;
  /** On-screen container width from onLayout. */
  containerWidth: number;
  /** On-screen container height from onLayout. */
  containerHeight: number;
}

// ---------------------------------------------------------------------------
// Coordinate scaling (letterbox-aware)
// ---------------------------------------------------------------------------

interface ScaleInfo {
  scale: number;
  offsetX: number;
  offsetY: number;
}

function computeScale(
  videoW: number, videoH: number,
  containerW: number, containerH: number,
): ScaleInfo {
  if (videoW <= 0 || videoH <= 0 || containerW <= 0 || containerH <= 0) {
    return { scale: 1, offsetX: 0, offsetY: 0 };
  }
  const videoAspect = videoW / videoH;
  const containerAspect = containerW / containerH;
  let scale: number, offsetX = 0, offsetY = 0;
  if (videoAspect > containerAspect) {
    scale = containerW / videoW;
    offsetY = (containerH - videoH * scale) / 2;
  } else {
    scale = containerH / videoH;
    offsetX = (containerW - videoW * scale) / 2;
  }
  return { scale, offsetX, offsetY };
}

// ---------------------------------------------------------------------------
// Single detection box — stable identity, fade-in once
// ---------------------------------------------------------------------------

const FADE_MS = 180;

const DetectionBox: React.FC<{
  detection: DetectionItem;
  scaleInfo: ScaleInfo;
}> = React.memo(({ detection, scaleInfo }) => {
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(opacity, {
      toValue: 1,
      duration: FADE_MS,
      useNativeDriver: true,
    }).start();
  }, []); // Only on mount — stable component keeps box visible on updates

  const { scale, offsetX, offsetY } = scaleInfo;
  const left   = detection.bbox.x      * scale + offsetX;
  const top    = detection.bbox.y      * scale + offsetY;
  const width  = detection.bbox.width  * scale;
  const height = detection.bbox.height * scale;

  const isKnown = !!detection.user_id;
  const borderColor = isKnown ? '#00E676' : '#FFD600';
  const labelBg     = isKnown ? 'rgba(0,0,0,0.72)' : 'rgba(60,40,0,0.80)';

  const displayName = detection.name
    ?? detection.student_id
    ?? (detection.user_id ? detection.user_id.slice(0, 8) : 'Unknown');

  const simPct = detection.similarity != null
    ? ` ${(detection.similarity * 100).toFixed(0)}%`
    : '';

  return (
    <Animated.View style={[s.box, { left, top, width, height, borderColor, opacity }]}>
      <View style={[s.label, { backgroundColor: labelBg }]}>
        <Text style={[s.labelText, { color: borderColor }]} numberOfLines={1}>
          {displayName}{simPct}
        </Text>
      </View>
    </Animated.View>
  );
}, (prev, next) =>
  // Only re-render if the detection data actually changed
  prev.detection.bbox.x === next.detection.bbox.x &&
  prev.detection.bbox.y === next.detection.bbox.y &&
  prev.detection.bbox.width === next.detection.bbox.width &&
  prev.detection.bbox.height === next.detection.bbox.height &&
  prev.detection.name === next.detection.name &&
  prev.detection.similarity === next.detection.similarity &&
  prev.scaleInfo.scale === next.scaleInfo.scale &&
  prev.scaleInfo.offsetX === next.scaleInfo.offsetX &&
  prev.scaleInfo.offsetY === next.scaleInfo.offsetY,
);

// ---------------------------------------------------------------------------
// Unknown face counter badge
// ---------------------------------------------------------------------------

const UnknownBadge: React.FC<{ count: number }> = React.memo(({ count }) => {
  if (count === 0) return null;
  return (
    <View style={s.unknownBadge}>
      <Text style={s.unknownBadgeText}>
        {count} unrecognized
      </Text>
    </View>
  );
});

// ---------------------------------------------------------------------------
// Overlay (main export)
// ---------------------------------------------------------------------------

export const DetectionOverlay: React.FC<DetectionOverlayProps> = React.memo(
  ({ detections, videoWidth, videoHeight, containerWidth, containerHeight }) => {
    const scaleInfo = useMemo(
      () => computeScale(videoWidth, videoHeight, containerWidth, containerHeight),
      [videoWidth, videoHeight, containerWidth, containerHeight],
    );

    const unknownCount = useMemo(
      () => detections.filter(d => !d.user_id).length,
      [detections],
    );

    if (!detections.length || containerWidth === 0 || containerHeight === 0) {
      return null;
    }

    return (
      <View style={StyleSheet.absoluteFill} pointerEvents="none">
        {detections.map((det, i) => (
          <DetectionBox
            key={det.user_id ?? `unknown-${i}`}
            detection={det}
            scaleInfo={scaleInfo}
          />
        ))}
        <UnknownBadge count={unknownCount} />
      </View>
    );
  },
);

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const s = StyleSheet.create({
  box: {
    position: 'absolute',
    borderWidth: 3,
    borderRadius: 3,
  },
  label: {
    position: 'absolute',
    top: -22,
    left: -1,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 3,
    maxWidth: 180,
  },
  labelText: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  unknownBadge: {
    position: 'absolute',
    bottom: 8,
    right: 8,
    backgroundColor: 'rgba(255,214,0,0.18)',
    borderWidth: 1,
    borderColor: '#FFD600',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  unknownBadgeText: {
    color: '#FFD600',
    fontSize: 11,
    fontWeight: '600',
  },
});
```

**Step 2: Type-check**

```bash
cd mobile && npx tsc --noEmit 2>&1 | grep DetectionOverlay
```
Expected: No errors.

**Step 3: Commit**

```bash
git add mobile/src/components/video/DetectionOverlay.tsx
git commit -m "feat(overlay): enterprise-grade detection boxes — 3px borders, dark labels, unknown badge, memoized render"
```

---

## Task 7: Mobile — Live Feed UX improvements

**Files:**
- Modify: `mobile/src/screens/faculty/FacultyLiveFeedScreen.tsx`

**Context:** The status bar only shows "Connected" / "Reconnecting". For a thesis defense and production use, faculty need to see: total detections active, unknown face count, and a "LIVE" indicator with a pulsing dot — the industry-standard security system aesthetic.

**Step 1: Add detection count and LIVE indicator to status bar**

In `FacultyLiveFeedScreen.tsx`:

1. Add `detectedCount` and `unknownCount` derived values:

```typescript
const detectedCount = useMemo(() => detections.length, [detections]);
const unknownCount = useMemo(
  () => detections.filter(d => !d.user_id).length,
  [detections],
);
```

2. Add a `LivePulse` animated component at the top of the file (before the main component):

```typescript
const LivePulse: React.FC = () => {
  const scale = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(scale, { toValue: 1.5, duration: 600, useNativeDriver: true }),
        Animated.timing(scale, { toValue: 1.0, duration: 600, useNativeDriver: true }),
      ])
    );
    anim.start();
    return () => anim.stop();
  }, []);

  return (
    <View style={livePulseStyles.container}>
      <Animated.View style={[livePulseStyles.dot, { transform: [{ scale }] }]} />
      <Text style={livePulseStyles.text}>LIVE</Text>
    </View>
  );
};

const livePulseStyles = StyleSheet.create({
  container: { flexDirection: 'row', alignItems: 'center' },
  dot: { width: 7, height: 7, borderRadius: 3.5, backgroundColor: '#F44336', marginRight: 5 },
  text: { color: '#F44336', fontSize: 11, fontWeight: '800', letterSpacing: 1 },
});
```

3. Update the status bar JSX to include detection count and LIVE pulse. Replace the right side of the status bar (currently shows "HLS Live") with:

```typescript
{/* Right side of status bar */}
<View style={styles.statusRight}>
  {isConnected && <LivePulse />}
  {detectedCount > 0 && (
    <Text variant="caption" weight="600" color={theme.colors.text.secondary} style={styles.detectionCount}>
      {detectedCount} detected
      {unknownCount > 0 ? ` · ${unknownCount} unknown` : ''}
    </Text>
  )}
</View>
```

4. Add `statusRight` and `detectionCount` to the `styles` StyleSheet:

```typescript
statusRight: {
  flexDirection: 'row',
  alignItems: 'center',
  gap: theme.spacing[3],
},
detectionCount: {
  marginLeft: theme.spacing[2],
},
```

Add the `Animated` import (if not already imported) and `useEffect`, `useRef` at the top.

**Step 2: Type-check**

```bash
cd mobile && npx tsc --noEmit 2>&1 | grep FacultyLiveFeed
```
Expected: No errors.

**Step 3: Commit**

```bash
git add mobile/src/screens/faculty/FacultyLiveFeedScreen.tsx
git commit -m "feat(live-feed): LIVE pulse indicator, detection count badge, unknown face count"
```

---

## Task 8: Final integration check and thesis-ready commit

**Step 1: Run full backend test suite**

```bash
cd backend && pytest --tb=short -q 2>&1 | tail -30
```
Expected: All previous tests pass. New tests (Tasks 1-4) pass.

**Step 2: Run TypeScript type-check on entire mobile project**

```bash
cd mobile && npx tsc --noEmit
```
Expected: No errors.

**Step 3: Verify config values are production-correct**

```bash
cd backend && python -c "
from app.config import settings
print('Batch size:', settings.RECOGNITION_MAX_BATCH_SIZE)
print('Recognition FPS:', settings.RECOGNITION_FPS)
print('HLS segment duration:', settings.HLS_SEGMENT_DURATION)
print('HLS playlist size:', settings.HLS_PLAYLIST_SIZE)
assert settings.RECOGNITION_MAX_BATCH_SIZE >= 50
assert settings.RECOGNITION_FPS >= 10.0
assert settings.HLS_SEGMENT_DURATION <= 1.0
assert settings.HLS_PLAYLIST_SIZE >= 3
print('All assertions passed.')
"
```

**Step 4: Final commit**

```bash
git add docs/plans/
git commit -m "docs: add enterprise live feed design doc and implementation plan"
```

---

## Summary of Changes

| File | Change | Impact |
|------|--------|--------|
| `config.py` | Batch 20→50, FPS 8→10, HLS 1s→0.5s, playlist 2→3 | 50+ faces per frame, 1.5-2.5s latency |
| `hls_service.py` | fMP4 segments + init.mp4, cleanup .m4s | Modern decoders, lower overhead |
| `hls.py` | Serve .m4s and .mp4 MIME types | fMP4 segments accessible |
| `recognition_service.py` | Exponential backoff 2→30s | No reconnect flooding |
| `live_stream.py` | NameCache class, 5min TTL, 10Hz | Thread-safe, 10Hz metadata |
| `useDetectionWebSocket.ts` | Backoff 1→30s, reset on success | No server hammering |
| `DetectionOverlay.tsx` | 3px borders, dark labels, unknown badge, memo | Enterprise visual quality |
| `FacultyLiveFeedScreen.tsx` | LIVE pulse, detection count, unknown count | Thesis-ready UI |
