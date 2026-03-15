"""
Local Camera Service

Runs MediaPipe face detection and feeds detections into the track fusion
service.  Supports two camera sources:

- **Webcam mode** (``CAMERA_SOURCE=0``): Opens the MacBook webcam, pushes
  video to mediamtx via FFmpeg RTSP, and runs detection on each frame.
- **External mode** (``CAMERA_SOURCE=mediamtx``): Reads from an external
  stream already being pushed to mediamtx (e.g. via ``dev-stream.sh camera``).
  No FFmpeg push — just pulls frames from mediamtx RTSP for detection.

Either way, the rest of the pipeline (track fusion, WebSocket broadcast,
mobile WebRTC) is identical.
"""

from __future__ import annotations

import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

from app.config import logger, settings
from app.services.edge_relay_service import track_fusion_service

# ── MediaPipe model download ────────────────────────────────────────────────

_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "models"
_MODEL_PATH = _MODEL_DIR / "blaze_face_short_range.tflite"
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_detector/blaze_face_short_range/float16/latest/"
    "blaze_face_short_range.tflite"
)


def _ensure_model() -> str:
    """Download the BlazeFace model if not already cached. Returns path."""
    if _MODEL_PATH.exists():
        return str(_MODEL_PATH)
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading BlazeFace model → %s", _MODEL_PATH)
    urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
    return str(_MODEL_PATH)

# ── Simple centroid tracker ──────────────────────────────────────────────────


@dataclass
class _TrackedObject:
    """Internal state for a tracked centroid."""

    track_id: int
    cx: float
    cy: float
    w: float
    h: float
    vx: float = 0.0
    vy: float = 0.0
    missed: int = 0
    last_time: float = field(default_factory=time.monotonic)


class _CentroidTracker:
    """
    Assigns stable track IDs via centroid distance matching.

    Simple and fast — no Kalman filter here; that lives in TrackFusionService.
    This just ensures detections in consecutive frames get the same ID.
    """

    def __init__(self, max_disappeared: int = 15, max_distance: float = 80.0):
        self._next_id = 1
        self._objects: dict[int, _TrackedObject] = {}
        self._max_disappeared = max_disappeared
        self._max_distance = max_distance

    def update(
        self, bboxes: list[tuple[float, float, float, float]]
    ) -> list[tuple[int, float, float, float, float, float, float]]:
        """
        Match incoming bboxes to existing tracks and return list of
        (track_id, x, y, w, h, vx, vy).
        """
        now = time.monotonic()

        # Compute centroids for incoming detections
        incoming: list[tuple[float, float, float, float, float, float]] = []
        for x, y, w, h in bboxes:
            incoming.append((x + w / 2, y + h / 2, x, y, w, h))

        if not incoming:
            # Mark all existing tracks as missed
            stale = []
            for tid, obj in self._objects.items():
                obj.missed += 1
                if obj.missed > self._max_disappeared:
                    stale.append(tid)
            for tid in stale:
                del self._objects[tid]
            return []

        if not self._objects:
            # All new tracks
            results = []
            for cx, cy, x, y, w, h in incoming:
                tid = self._next_id
                self._next_id += 1
                self._objects[tid] = _TrackedObject(
                    track_id=tid, cx=cx, cy=cy, w=w, h=h, last_time=now
                )
                results.append((tid, x, y, w, h, 0.0, 0.0))
            return results

        # Build cost matrix (Euclidean distance between centroids)
        obj_ids = list(self._objects.keys())
        obj_list = [self._objects[tid] for tid in obj_ids]

        costs = np.zeros((len(obj_list), len(incoming)), dtype=np.float64)
        for i, obj in enumerate(obj_list):
            for j, (cx, cy, *_) in enumerate(incoming):
                costs[i, j] = ((obj.cx - cx) ** 2 + (obj.cy - cy) ** 2) ** 0.5

        # Greedy matching (good enough for <20 faces)
        matched_obj: set[int] = set()
        matched_det: set[int] = set()
        results: list[tuple[int, float, float, float, float, float, float]] = [
            None
        ] * len(incoming)  # type: ignore[list-item]

        # Sort by cost ascending and greedily assign
        flat_indices = np.argsort(costs, axis=None)
        for flat_idx in flat_indices:
            i = int(flat_idx // len(incoming))
            j = int(flat_idx % len(incoming))
            if i in matched_obj or j in matched_det:
                continue
            if costs[i, j] > self._max_distance:
                break
            matched_obj.add(i)
            matched_det.add(j)

            obj = obj_list[i]
            cx, cy, x, y, w, h = incoming[j]
            dt = now - obj.last_time
            if dt > 0:
                vx = (cx - obj.cx) / dt
                vy = (cy - obj.cy) / dt
            else:
                vx, vy = obj.vx, obj.vy

            obj.cx, obj.cy = cx, cy
            obj.w, obj.h = w, h
            obj.vx, obj.vy = vx, vy
            obj.missed = 0
            obj.last_time = now
            results[j] = (obj.track_id, x, y, w, h, vx, vy)

        # Handle unmatched detections → new tracks
        for j in range(len(incoming)):
            if j not in matched_det:
                cx, cy, x, y, w, h = incoming[j]
                tid = self._next_id
                self._next_id += 1
                self._objects[tid] = _TrackedObject(
                    track_id=tid, cx=cx, cy=cy, w=w, h=h, last_time=now
                )
                results[j] = (tid, x, y, w, h, 0.0, 0.0)

        # Handle unmatched existing tracks → increment missed
        stale = []
        for i in range(len(obj_list)):
            if i not in matched_obj:
                obj_list[i].missed += 1
                if obj_list[i].missed > self._max_disappeared:
                    stale.append(obj_ids[i])
        for tid in stale:
            del self._objects[tid]

        return [r for r in results if r is not None]


# ── Local Camera Service ─────────────────────────────────────────────────────


class LocalCameraService:
    """
    Runs MediaPipe face detection and feeds detections into track_fusion_service.

    Two modes based on ``CAMERA_SOURCE``:
    - Integer (e.g. ``"0"``) → webcam mode: capture + FFmpeg RTSP push + detection
    - ``"mediamtx"`` → external mode: pull from mediamtx RTSP for detection only

    Thread-safe: capture loop runs in a background thread with async
    start/stop API.
    """

    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Latest frame for recognition service
        self._frame: np.ndarray | None = None
        self._frame_lock = threading.Lock()

        self._cap: cv2.VideoCapture | None = None
        self._ffmpeg_proc: subprocess.Popen | None = None
        self._tracker = _CentroidTracker()

        # MediaPipe face detector (Tasks API, initialized in capture thread)
        self._detector: mp.tasks.vision.FaceDetector | None = None

        # Room ID for this local camera session
        self._room_id: str = "local"

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._running

    @property
    def is_external(self) -> bool:
        """True when reading from an external stream (not the local webcam)."""
        try:
            int(settings.CAMERA_SOURCE)
            return False
        except ValueError:
            return True

    def get_latest_frame(self) -> np.ndarray | None:
        """Return the most recent captured frame (BGR), or None."""
        with self._frame_lock:
            return self._frame.copy() if self._frame is not None else None

    async def start(self, room_id: str = "local") -> None:
        """Start the capture loop in a background thread."""
        with self._lock:
            if self._running:
                logger.warning("LocalCameraService already running")
                return
            self._room_id = room_id
            self._running = True
            self._thread = threading.Thread(
                target=self._capture_loop,
                name="local-camera",
                daemon=True,
            )
            self._thread.start()

        mode = "external (mediamtx pull)" if self.is_external else f"webcam ({settings.CAMERA_SOURCE})"
        logger.info(
            "LocalCameraService started (room=%s, mode=%s, fps=%.1f)",
            room_id,
            mode,
            settings.LOCAL_DETECTION_FPS,
        )

    async def stop(self) -> None:
        """Signal the capture loop to stop and wait for the thread."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

        logger.info("LocalCameraService stopped")

    # ── Capture loop (runs in background thread) ─────────────────────────

    def _capture_loop(self) -> None:
        """Main loop: open camera, detect faces, optionally push RTSP, feed fusion."""
        import os

        # Suppress non-fatal H.264 decode warnings that flood the console
        os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "error"

        try:
            # In external mode, the stream might not exist in mediamtx yet
            # (dev-stream.sh hasn't started). Retry up to 60 seconds.
            if self.is_external:
                max_wait = 60.0
                waited = 0.0
                while self._running and waited < max_wait:
                    self._open_camera()
                    if self._cap is not None and self._cap.isOpened():
                        break
                    if self._cap is not None:
                        self._cap.release()
                        self._cap = None
                    if waited == 0:
                        logger.info(
                            "LocalCameraService: waiting for external stream at "
                            "rtsp://localhost:8554/%s (start dev-stream.sh)",
                            self._room_id,
                        )
                    time.sleep(2.0)
                    waited += 2.0
            else:
                self._open_camera()

            if self._cap is None or not self._cap.isOpened():
                logger.error("LocalCameraService: failed to open camera source")
                self._running = False
                return

            frame_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = settings.LOCAL_DETECTION_FPS

            # Only push via FFmpeg in webcam mode (external streams are
            # already being pushed to mediamtx by dev-stream.sh or RPi)
            if not self.is_external:
                self._start_ffmpeg(frame_w, frame_h, fps)

                # Initialize MediaPipe face detector (Tasks API)
                # Only needed in webcam mode — external/CCTV uses InsightFace
                # via recognition_service (BlazeFace short-range fails at >2 m)
                model_path = _ensure_model()
                base_options = mp.tasks.BaseOptions(model_asset_path=model_path)
                detector_options = mp.tasks.vision.FaceDetectorOptions(
                    base_options=base_options,
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    min_detection_confidence=0.5,
                )
                self._detector = mp.tasks.vision.FaceDetector.create_from_options(
                    detector_options
                )

            mode_label = "external" if self.is_external else "webcam"
            target_interval = 1.0 / fps
            logger.info(
                "LocalCameraService: capture loop started (%dx%d @ %.0f FPS, %s)",
                frame_w,
                frame_h,
                fps,
                mode_label,
            )

            while self._running:
                loop_start = time.monotonic()

                ret, frame = self._cap.read()
                if not ret:
                    logger.warning("LocalCameraService: frame read failed, retrying")
                    time.sleep(0.1)
                    continue

                # Skip corrupted frames (nearly all black or all white)
                mean_val = frame.mean()
                if mean_val < 3.0 or mean_val > 252.0:
                    time.sleep(target_interval * 0.5)
                    continue

                # Store latest frame for recognition service
                with self._frame_lock:
                    self._frame = frame

                # Push frame to FFmpeg → mediamtx RTSP (webcam mode only)
                if not self.is_external:
                    self._push_frame(frame)

                # In external mode (CCTV), skip MediaPipe detection —
                # BlazeFace short-range fails at CCTV distances (>2 m).
                # InsightFace SCRFD (via recognition_service) handles
                # detection + identity and feeds track_fusion_service
                # from the live_stream router push loop instead.
                if not self.is_external:
                    detections = self._detect_faces(frame, frame_w, frame_h)
                    track_fusion_service.update_from_edge(
                        self._room_id,
                        detections,
                        frame_w,
                        frame_h,
                    )

                # Maintain target FPS
                elapsed = time.monotonic() - loop_start
                sleep_time = target_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except Exception:
            logger.exception("LocalCameraService: capture loop crashed")
        finally:
            self._cleanup()

    def _detect_faces(
        self, frame: np.ndarray, frame_w: int, frame_h: int
    ) -> list[dict]:
        """Run MediaPipe face detection and return tracked detections."""
        if self._detector is None:
            return []

        # MediaPipe Tasks API expects RGB mp.Image
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._detector.detect(mp_image)

        bboxes: list[tuple[float, float, float, float]] = []
        confidences: list[float] = []

        for det in result.detections:
            bb = det.bounding_box
            # bounding_box fields: origin_x, origin_y, width, height (pixels)
            x = bb.origin_x
            y = bb.origin_y
            w = bb.width
            h = bb.height
            # Clamp to frame bounds
            x = max(0, x)
            y = max(0, y)
            w = min(w, frame_w - x)
            h = min(h, frame_h - y)
            if w > 0 and h > 0:
                bboxes.append((float(x), float(y), float(w), float(h)))
                score = det.categories[0].score if det.categories else 0.5
                confidences.append(score)

        # Update centroid tracker for stable IDs
        tracked = self._tracker.update(bboxes)

        # Build detection dicts matching track_fusion_service format
        detections: list[dict] = []
        for i, (track_id, x, y, w, h, vx, vy) in enumerate(tracked):
            # Find matching confidence (by bbox proximity)
            conf = confidences[i] if i < len(confidences) else 0.5
            detections.append(
                {
                    "track_id": track_id,
                    "bbox": [x, y, w, h],
                    "confidence": float(conf),
                    "velocity": [vx, vy],
                }
            )

        return detections

    # ── FFmpeg RTSP push (webcam mode only) ───────────────────────────────

    def _start_ffmpeg(self, width: int, height: int, fps: float) -> None:
        """Start an FFmpeg subprocess to push rawvideo → RTSP."""
        rtsp_url = f"{settings.MEDIAMTX_RTSP_URL}/{self._room_id}"
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}",
            "-r", str(fps),
            "-i", "-",
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-profile:v", "baseline",
            "-level:v", "3.1",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-g", str(int(fps)),
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            rtsp_url,
        ]
        try:
            self._ffmpeg_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info(
                "LocalCameraService: FFmpeg RTSP push started → %s", rtsp_url
            )
        except FileNotFoundError:
            logger.warning(
                "LocalCameraService: ffmpeg not found, RTSP push disabled"
            )
            self._ffmpeg_proc = None

    def _push_frame(self, frame: np.ndarray) -> None:
        """Write a raw BGR frame to FFmpeg's stdin."""
        if self._ffmpeg_proc is None or self._ffmpeg_proc.stdin is None:
            return
        try:
            self._ffmpeg_proc.stdin.write(frame.tobytes())
        except BrokenPipeError:
            logger.warning("LocalCameraService: FFmpeg pipe broken, disabling RTSP push")
            self._ffmpeg_proc = None

    # ── Camera / cleanup ─────────────────────────────────────────────────

    def _open_camera(self) -> None:
        """Open the video source (webcam index or mediamtx RTSP)."""
        import os

        source = settings.CAMERA_SOURCE
        try:
            index = int(source)
            self._cap = cv2.VideoCapture(index)
        except ValueError:
            # External mode: read from mediamtx RTSP for this room.
            # Force TCP transport and discard corrupt frames to avoid
            # H.264 decode errors that prevent face detection.
            rtsp_url = f"{settings.MEDIAMTX_RTSP_URL}/{self._room_id}"
            logger.info(
                "LocalCameraService: external mode — pulling from %s", rtsp_url
            )
            prev = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS", "")
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                "rtsp_transport;tcp"
                "|stimeout;5000000"
                "|err_detect;ignore_err"
                "|fflags;discardcorrupt"
            )
            self._cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            # Restore previous env var
            if prev:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = prev
            else:
                os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)

            if self._cap is not None and self._cap.isOpened():
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def _cleanup(self) -> None:
        """Release camera and FFmpeg resources."""
        if self._detector is not None:
            self._detector.close()
            self._detector = None

        if self._cap is not None:
            self._cap.release()
            self._cap = None

        if self._ffmpeg_proc is not None:
            try:
                if self._ffmpeg_proc.stdin:
                    self._ffmpeg_proc.stdin.close()
                self._ffmpeg_proc.terminate()
                self._ffmpeg_proc.wait(timeout=5)
            except Exception:
                self._ffmpeg_proc.kill()
            self._ffmpeg_proc = None

        with self._frame_lock:
            self._frame = None

        self._running = False
        logger.info("LocalCameraService: resources cleaned up")


# Module-level singleton
local_camera_service = LocalCameraService()
