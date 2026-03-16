"""
Compositor Service — Server-Side Video Compositing

Draws bounding boxes directly onto video frames before encoding, eliminating
the video-vs-metadata sync problem. Enterprise video analytics systems
(Genetec, Milestone) use this same approach.

Architecture (2 threads):
- Compositor thread (15 FPS): read frame → share with detector → draw tracks → push FFmpeg
- Detector thread (~5 FPS): grab shared frame → InsightFace SCRFD+ArcFace → update fusion

The compositor owns the camera. The detector reads from a shared frame buffer.
The compositor never blocks on detection → smooth output guaranteed.
"""

import subprocess
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

from app.config import logger, settings


# ── Drawing constants ────────────────────────────────────────────────────────

_GREEN = (0, 200, 0)
_YELLOW = (0, 200, 200)
_WHITE = (255, 255, 255)
_FONT = cv2.FONT_HERSHEY_SIMPLEX
_FONT_SCALE = 0.55
_FONT_THICKNESS = 1
_BOX_THICKNESS = 2


@dataclass
class TrackSnapshot:
    """Lightweight copy of a fused track for drawing."""
    bbox: list[float]  # [x, y, w, h] in detection coordinates
    name: str | None = None
    student_id: str | None = None
    user_id: str | None = None
    similarity: float | None = None
    is_confirmed: bool = False


class CompositorService:
    """
    Reads camera RTSP, draws bounding boxes onto frames, pushes composited
    video to mediamtx via FFmpeg for WebRTC delivery.
    """

    def __init__(self):
        self._stop_event = threading.Event()
        self._capture: cv2.VideoCapture | None = None
        self._ffmpeg_proc: subprocess.Popen | None = None
        self._room_id: str = ""

        # Shared frame buffer: compositor writes, detector reads
        self._frame_lock = threading.Lock()
        self._shared_frame: np.ndarray | None = None

        # Track state: detector writes, compositor reads
        self._track_lock = threading.Lock()
        self._tracks: list[TrackSnapshot] = []
        self._det_frame_w: int = 0
        self._det_frame_h: int = 0

        # Detection summary: detector writes, WebSocket reads
        self._summary_lock = threading.Lock()
        self._detected: list[dict] = []
        self._total_unknown: int = 0

        self._compositor_thread: threading.Thread | None = None
        self._detector_thread: threading.Thread | None = None

    # ── Public API ────────────────────────────────────────────────────────

    def start(self, room_id: str) -> bool:
        """Open camera, start FFmpeg, launch both threads."""
        self._room_id = room_id
        self._stop_event.clear()

        camera_url = settings.COMPOSITED_CAMERA_URL
        if not camera_url:
            logger.error("CompositorService: COMPOSITED_CAMERA_URL not set")
            return False

        self._capture = cv2.VideoCapture(camera_url, cv2.CAP_FFMPEG)
        if not self._capture.isOpened():
            logger.error("CompositorService: failed to open camera at %s", camera_url)
            return False

        w = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = settings.COMPOSITED_FPS
        logger.info("CompositorService: camera opened %dx%d, output FPS=%.1f", w, h, fps)

        self._start_ffmpeg(w, h, fps)

        self._compositor_thread = threading.Thread(
            target=self._compositor_loop, args=(w, h, fps), daemon=True,
            name="compositor",
        )
        self._detector_thread = threading.Thread(
            target=self._detector_loop, daemon=True,
            name="detector",
        )
        self._compositor_thread.start()
        self._detector_thread.start()
        return True

    def stop(self):
        """Signal threads to stop, cleanup resources."""
        self._stop_event.set()

        for t in (self._compositor_thread, self._detector_thread):
            if t and t.is_alive():
                t.join(timeout=5.0)

        if self._ffmpeg_proc:
            try:
                self._ffmpeg_proc.stdin.close()
            except Exception:
                pass
            self._ffmpeg_proc.terminate()
            self._ffmpeg_proc = None

        if self._capture:
            self._capture.release()
            self._capture = None

        # Cleanup fusion state
        from app.services.edge_relay_service import track_fusion_service
        track_fusion_service.cleanup_room(self._room_id)

        logger.info("CompositorService: stopped for room %s", self._room_id)

    def get_summary(self) -> dict:
        """Thread-safe getter for detection summary (for WebSocket push)."""
        with self._summary_lock:
            return {
                "detected": list(self._detected),
                "total_detected": len(self._detected),
                "total_unknown": self._total_unknown,
            }

    # ── FFmpeg RTSP push ──────────────────────────────────────────────────

    def _start_ffmpeg(self, width: int, height: int, fps: float) -> None:
        rtsp_url = f"{settings.MEDIAMTX_RTSP_URL}/{self._room_id}"
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24", "-s", f"{width}x{height}",
            "-r", str(fps), "-i", "-",
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-profile:v", "baseline",
            "-level:v", "3.1", "-preset", "ultrafast",
            "-tune", "zerolatency", "-g", str(int(fps)),
            "-f", "rtsp", "-rtsp_transport", "tcp", rtsp_url,
        ]
        try:
            self._ffmpeg_proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            logger.info("CompositorService: FFmpeg → %s", rtsp_url)
        except FileNotFoundError:
            logger.error("CompositorService: ffmpeg not found")
            self._ffmpeg_proc = None

    def _push_frame(self, frame: np.ndarray) -> None:
        if self._ffmpeg_proc is None or self._ffmpeg_proc.stdin is None:
            return
        try:
            self._ffmpeg_proc.stdin.write(frame.tobytes())
        except BrokenPipeError:
            logger.warning("CompositorService: FFmpeg pipe broken")
            self._ffmpeg_proc = None

    # ── Compositor thread (15 FPS) ────────────────────────────────────────

    def _compositor_loop(self, width: int, height: int, fps: float) -> None:
        """Read frame → share with detector → draw tracks → push to FFmpeg."""
        interval = 1.0 / fps
        logger.info("CompositorService: compositor started (%.0f FPS)", fps)

        while not self._stop_event.is_set():
            t0 = time.monotonic()

            ret, frame = self._capture.read()
            if not ret:
                logger.warning("CompositorService: frame read failed, reconnecting...")
                time.sleep(1.0)
                self._capture.release()
                self._capture = cv2.VideoCapture(
                    settings.COMPOSITED_CAMERA_URL, cv2.CAP_FFMPEG
                )
                continue

            # Share frame with detector thread (non-blocking swap)
            with self._frame_lock:
                self._shared_frame = frame.copy()

            # Read current track state
            with self._track_lock:
                tracks = list(self._tracks)
                det_w, det_h = self._det_frame_w, self._det_frame_h

            # Draw bounding boxes onto the frame
            if tracks and det_w > 0 and det_h > 0:
                scale_x = width / det_w
                scale_y = height / det_h
                self._draw_tracks(frame, tracks, scale_x, scale_y)

            self._push_frame(frame)

            elapsed = time.monotonic() - t0
            if elapsed < interval:
                time.sleep(interval - elapsed)

        logger.info("CompositorService: compositor stopped")

    def _draw_tracks(
        self, frame: np.ndarray, tracks: list[TrackSnapshot],
        scale_x: float, scale_y: float,
    ) -> None:
        for t in tracks:
            if not t.is_confirmed:
                continue

            x, y, w, h = t.bbox
            x1, y1 = int(x * scale_x), int(y * scale_y)
            x2, y2 = int((x + w) * scale_x), int((y + h) * scale_y)

            if t.user_id and t.name:
                color = _GREEN
                # Show first name only to keep label short
                label = t.name.split()[0] if t.name else "Unknown"
            else:
                color = _YELLOW
                label = "Unknown"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, _BOX_THICKNESS)

            (tw, th), baseline = cv2.getTextSize(label, _FONT, _FONT_SCALE, _FONT_THICKNESS)
            label_y = max(y1 - 6, th + 4)
            cv2.rectangle(frame, (x1, label_y - th - 4), (x1 + tw + 4, label_y + baseline), color, cv2.FILLED)
            cv2.putText(frame, label, (x1 + 2, label_y - 2), _FONT, _FONT_SCALE, _WHITE, _FONT_THICKNESS, cv2.LINE_AA)

    # ── Detector thread (~5 FPS async) ────────────────────────────────────

    def _detector_loop(self) -> None:
        """Grab shared frames, run InsightFace, update track state."""
        from app.services.recognition_service import recognition_service
        from app.services.edge_relay_service import track_fusion_service
        from app.routers.live_stream import _name_cache, _enrich_and_cache, _recognition_tracker
        from app.database import SessionLocal

        recognition_service._ensure_ml()

        detect_every_n = settings.COMPOSITED_DETECT_EVERY_N
        frame_count = 0
        detect_interval = detect_every_n / settings.COMPOSITED_FPS

        logger.info("CompositorService: detector started (every %d frames ≈ %.1fs)",
                     detect_every_n, detect_interval)

        while not self._stop_event.is_set():
            frame_count += 1

            # Between detection frames, just advance Kalman and update snapshots
            if frame_count % detect_every_n != 0:
                track_fusion_service.predict(self._room_id, dt=1.0 / settings.COMPOSITED_FPS)
                self._refresh_snapshots(track_fusion_service)
                time.sleep(1.0 / settings.COMPOSITED_FPS)
                continue

            # Grab the latest frame from shared buffer
            with self._frame_lock:
                frame = self._shared_frame
                self._shared_frame = None  # consume it

            if frame is None:
                time.sleep(0.05)
                continue

            # Run InsightFace detection + recognition
            detections, det_w, det_h = recognition_service._process_frame_ml(frame)

            if not detections:
                self._refresh_snapshots(track_fusion_service)
                continue

            # Enrich with student names
            det_dicts = [d.to_dict() for d in detections]
            det_dicts = _enrich_and_cache(det_dicts, detections, SessionLocal)

            # Assign stable track IDs via IoU matching
            tracked = _recognition_tracker.assign(self._room_id, det_dicts)

            # Build edge-format detections for track fusion
            edge_dets = []
            for tid, det in tracked:
                bbox = det.get("bbox", {})
                edge_dets.append({
                    "track_id": tid,
                    "bbox": [bbox.get("x", 0), bbox.get("y", 0),
                             bbox.get("width", 0), bbox.get("height", 0)],
                    "confidence": det.get("confidence", 0.5),
                    "velocity": [0.0, 0.0],
                })

            track_fusion_service.update_from_edge(self._room_id, edge_dets, det_w, det_h)

            # Push identity for recognized faces
            for tid, det in tracked:
                if det.get("user_id") and det.get("name"):
                    track_fusion_service.update_identity(
                        self._room_id, tid,
                        det["user_id"], det.get("name", ""),
                        det.get("student_id", ""), det.get("similarity", 0.0),
                    )

            self._refresh_snapshots(track_fusion_service)

        logger.info("CompositorService: detector stopped")

    def _refresh_snapshots(self, fusion_svc) -> None:
        """Copy fused tracks into snapshots for drawing + summary."""
        tracks_dicts = fusion_svc.get_tracks(self._room_id)
        fw, fh = fusion_svc.get_room_dimensions(self._room_id)

        snapshots = []
        detected = []
        unknown_count = 0

        for td in tracks_dicts:
            snap = TrackSnapshot(
                bbox=td["bbox"],
                name=td.get("name"),
                student_id=td.get("student_id"),
                user_id=td.get("user_id"),
                similarity=td.get("similarity"),
                is_confirmed=(td.get("state") == "confirmed"),
            )
            snapshots.append(snap)

            if snap.is_confirmed:
                if snap.user_id and snap.name:
                    detected.append({
                        "user_id": snap.user_id,
                        "name": snap.name,
                        "student_id": snap.student_id or "",
                        "similarity": round(snap.similarity or 0.0, 3),
                    })
                else:
                    unknown_count += 1

        with self._track_lock:
            self._tracks = snapshots
            if fw > 0:
                self._det_frame_w = fw
            if fh > 0:
                self._det_frame_h = fh

        with self._summary_lock:
            self._detected = detected
            self._total_unknown = unknown_count
