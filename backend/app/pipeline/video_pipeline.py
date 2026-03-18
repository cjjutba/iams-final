"""Unified video analytics pipeline -- RTSP in, annotated RTSP out.

Reads RTSP from mediamtx, runs face detection + tracking (ByteTrack),
draws annotations, and publishes annotated stream.

Detection: YuNet (default, ~2-5ms CPU) or InsightFace SCRFD (legacy).
Identity labels read from Redis cache written by AttendanceScanEngine.

Designed to run as a separate process per room.
"""

import json
import math
import time
from datetime import datetime
from typing import Any

import cv2
import numpy as np
import supervision as sv

from app.config import logger, settings
from app.pipeline.ffmpeg_publisher import FFmpegPublisher
from app.pipeline.frame_annotator import FrameAnnotator
from app.pipeline.rtsp_reader import RTSPReader


class VideoAnalyticsPipeline:
    """Single-room video analytics pipeline.

    Combines RTSPReader (input) -> SCRFD detection -> ByteTrack tracking ->
    ArcFace recognition -> FrameAnnotator (drawing) -> FFmpegPublisher (output)
    into a single synchronous processing loop.

    Args:
        config: Pipeline configuration dict with keys:
            ``room_id``, ``rtsp_source``, ``rtsp_target``, ``width``,
            ``height``, ``fps``, ``room_name``, ``det_model``.
            Optional: ``subject``, ``professor``, ``total_enrolled``.
    """

    def __init__(self, config: dict) -> None:
        self.config = config
        self.room_id: str = config["room_id"]
        self._session_id: str | None = config.get("session_id")
        self._running = False

        # Sub-components (initialized on start)
        self._reader: RTSPReader | None = None
        self._publisher: FFmpegPublisher | None = None
        self._annotator: FrameAnnotator | None = None
        self._tracker: sv.ByteTrack | None = None
        self._detector = None  # InsightFace model (loaded on start)
        self._faiss = None     # FAISSManager (loaded on start)

        # State
        self._identities: dict[int, dict] = {}       # track_id -> identity info
        self._track_start_times: dict[int, float] = {}  # track_id -> first-seen time
        self._confirmed_track_ids: set[int] = set()   # tracks with 3+ frames
        self._track_frame_counts: dict[int, int] = {} # track_id -> frames seen
        self._hud_info: dict = {
            "room_name": config.get("room_name", ""),
            "timestamp": "",
            "subject": config.get("subject", ""),
            "professor": config.get("professor", ""),
            "present_count": 0,
            "total_count": config.get("total_enrolled", 0),
        }

        # Redis client (set externally before start)
        self._redis = None

    # ------------------------------------------------------------------
    # Detection list builder (used by FrameAnnotator)
    # ------------------------------------------------------------------

    def _build_detection_list(self, tracked: sv.Detections) -> list[dict]:
        """Convert tracked detections to the dict format expected by FrameAnnotator.

        Each dict contains: ``bbox``, ``name``, ``student_id``, ``confidence``,
        ``track_state``, ``track_id``, ``duration_sec``.
        """
        now = time.time()
        result: list[dict] = []
        if tracked.tracker_id is None:
            return result

        for i, track_id in enumerate(tracked.tracker_id):
            tid = int(track_id)
            bbox = tracked.xyxy[i].tolist()

            # Track start time
            if tid not in self._track_start_times:
                self._track_start_times[tid] = now

            # Frame count for confirmation
            self._track_frame_counts[tid] = self._track_frame_counts.get(tid, 0) + 1
            if self._track_frame_counts[tid] >= 3:
                self._confirmed_track_ids.add(tid)

            # Identity lookup
            identity = self._identities.get(tid)
            if identity:
                state = "confirmed"
            elif tid in self._confirmed_track_ids:
                state = "unknown"
            else:
                state = "new"

            result.append({
                "bbox": tuple(int(v) for v in bbox),
                "name": identity["name"] if identity else None,
                "student_id": identity.get("student_id") if identity else None,
                "confidence": identity["confidence"] if identity else 0.0,
                "track_state": state,
                "track_id": tid,
                "duration_sec": now - self._track_start_times[tid],
            })
        return result

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialize all sub-components and enter the processing loop.

        This method blocks until ``stop()`` is called from another thread
        or the process is terminated.
        """
        cfg = self.config
        w, h, fps = cfg["width"], cfg["height"], cfg["fps"]

        logger.info(f"[Pipeline:{self.room_id}] Starting -- {w}x{h}@{fps}fps")

        # RTSP reader
        self._reader = RTSPReader(cfg["rtsp_source"], target_fps=fps, width=w, height=h)
        self._reader.start()

        # FFmpeg publisher
        self._publisher = FFmpegPublisher(cfg["rtsp_target"], w, h, fps)
        self._publisher.start()

        # Annotator
        self._annotator = FrameAnnotator(w, h)

        # ByteTrack — tuned for small/distant faces with movement
        self._tracker = sv.ByteTrack(
            track_activation_threshold=0.15,   # accept weak detections (small faces)
            lost_track_buffer=fps * 3,         # survive 3 seconds of missed detections
            minimum_matching_threshold=0.2,    # very low IoU for small faces that shift
            frame_rate=fps,
            minimum_consecutive_frames=1,
        )

        # ML models (deferred import to avoid loading at module level)
        det_type = cfg.get("detector", settings.PIPELINE_DETECTOR)
        try:
            if det_type == "yunet":
                from pathlib import Path

                from app.services.ml.yunet_detector import YuNetDetector

                model_path = Path(__file__).parent.parent.parent / settings.YUNET_MODEL_PATH
                self._detector = YuNetDetector(
                    model_path=str(model_path),
                    score_threshold=settings.YUNET_SCORE_THRESHOLD,
                    nms_threshold=settings.YUNET_NMS_THRESHOLD,
                )
                self._detector.load(w, h)
                self._faiss = None
                logger.info(f"[Pipeline:{self.room_id}] Using YuNet detector (CPU-optimized)")
            else:
                from app.services.ml.faiss_manager import faiss_manager
                from app.services.ml.insightface_model import insightface_model

                if insightface_model.app is None:
                    insightface_model.load_model()
                self._detector = insightface_model
                self._faiss = faiss_manager
                logger.info(f"[Pipeline:{self.room_id}] Using InsightFace detector (legacy)")
        except Exception as e:
            logger.error(f"[Pipeline:{self.room_id}] ML model load failed: {e}")

        self._running = True
        self._run_loop()

    def _run_loop(self) -> None:
        """Main processing loop -- read, detect/track, recognize, annotate, publish.

        Detection runs every ``det_interval`` frames (configured via
        ``PIPELINE_DET_INTERVAL``).  On intermediate frames, ByteTrack predicts
        track positions using its internal Kalman filter.
        """
        cfg = self.config
        fps = cfg["fps"]
        frame_interval = 1.0 / fps
        det_interval = cfg.get("det_interval", settings.PIPELINE_DET_INTERVAL)
        comp_h, comp_w = cfg["height"], cfg["width"]
        # Run detection at full compositing resolution.
        # Downscaling loses small/distant faces — not worth the CPU savings
        # given we already limit FPS via det_interval.
        det_w, det_h = comp_w, comp_h
        scale = 1.0

        last_state_push = 0.0
        last_recognition_check = 0.0
        last_publisher_check = time.time()
        frame_count = 0

        while self._running:
            loop_start = time.time()

            # Read latest frame (full resolution)
            frame = self._reader.read() if self._reader else None
            if frame is None:
                time.sleep(0.01)
                continue

            # Run detection EVERY frame — YuNet is fast enough (~2-5ms)
            # This ensures bounding boxes follow moving faces in real-time
            detections = self._detect_faces(frame, scale=scale)
            tracked = self._tracker.update_with_detections(detections)

            if frame_count % 200 == 0:
                logger.debug(
                    f"[Pipeline:{self.room_id}] frame {frame_count}: "
                    f"faces={len(detections)}, tracks="
                    f"{len(tracked.tracker_id) if tracked.tracker_id is not None else 0}"
                )

            # Recognize new/unidentified tracks (throttled to every 0.5s)
            now = time.time()
            if now - last_recognition_check > 0.5:
                self._recognize_new_tracks(frame, tracked)
                last_recognition_check = now

            # Clean up stale identities
            self._cleanup_stale_tracks(tracked)

            # Build detection list for annotator
            det_list = self._build_detection_list(tracked)

            if frame_count % (det_interval * 60) == 0:
                logger.info(
                    f"[Pipeline:{self.room_id}] frame {frame_count}: "
                    f"{len(det_list)} tracks, publisher={'alive' if self._publisher and self._publisher.is_alive else 'dead'}"
                )

            # Update HUD
            self._hud_info["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._hud_info["present_count"] = sum(
                1 for d in det_list if d["name"] is not None
            )

            # Annotate
            annotated = self._annotator.annotate(frame, det_list, self._hud_info)

            # Publish — check health every 10s even if writes appear to succeed
            if self._publisher:
                if not self._publisher.write_frame(annotated):
                    logger.warning(f"[Pipeline:{self.room_id}] Publisher write failed, restarting")
                    self._restart_publisher()
                elif now - last_publisher_check > 10.0:
                    if not self._publisher.is_alive:
                        logger.warning(f"[Pipeline:{self.room_id}] Publisher process died, restarting")
                        self._restart_publisher()
                    last_publisher_check = now

            # Publish state to Redis (throttled to 1 Hz)
            if self._redis and now - last_state_push > 1.0:
                self._publish_state_to_redis(det_list)
                last_state_push = now

            # Frame pacing
            elapsed = time.time() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

            frame_count += 1

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def _detect_faces(self, frame: np.ndarray, scale: float = 1.0) -> sv.Detections:
        """Run face detection and return supervision Detections.

        Supports two detector backends:
        - YuNetDetector: has detect() method, returns sv.Detections directly
        - InsightFaceModel: has get_faces() method, returns list[DetectedFace]
        """
        if self._detector is None:
            return sv.Detections.empty()

        try:
            # YuNet path: returns sv.Detections directly
            if hasattr(self._detector, "detect"):
                return self._detector.detect(frame, scale=scale)

            # Legacy InsightFace path: convert DetectedFace → sv.Detections
            faces = self._detector.get_faces(frame)
            if not faces:
                return sv.Detections.empty()

            bboxes = np.array(
                [[f.x, f.y, f.x + f.width, f.y + f.height] for f in faces],
                dtype=np.float32,
            )
            if scale != 1.0:
                bboxes *= scale
            scores = np.array([f.confidence for f in faces], dtype=np.float32)
            return sv.Detections(xyxy=bboxes, confidence=scores)
        except Exception as e:
            logger.error(f"[Pipeline:{self.room_id}] Detection error: {e}")
            return sv.Detections.empty()

    # ------------------------------------------------------------------
    # Identity cache (Redis bridge from Attendance Engine)
    # ------------------------------------------------------------------

    def _read_identity_cache(self) -> dict[str, dict[str, Any]]:
        """Read cached identities written by the Attendance Engine.

        Returns:
            Mapping of ``user_id`` to identity dict (name, confidence, bbox).
            Empty dict when Redis is unavailable, session_id is unset, or
            the key does not exist.
        """
        if self._redis is None or self._session_id is None:
            return {}

        try:
            key = f"attendance:{self.room_id}:{self._session_id}:identities"
            raw: dict = self._redis.hgetall(key)
            if not raw:
                return {}

            result: dict[str, dict[str, Any]] = {}
            for field, value in raw.items():
                uid = field.decode() if isinstance(field, bytes) else field
                val = value.decode() if isinstance(value, bytes) else value
                result[uid] = json.loads(val)
            return result
        except Exception as e:
            logger.debug(f"[Pipeline:{self.room_id}] Identity cache read error: {e}")
            return {}

    @staticmethod
    def _match_from_cache(
        xyxy: tuple[int, int, int, int],
        cached_identities: dict[str, dict[str, Any]],
        max_distance: float = 100.0,
    ) -> dict[str, Any] | None:
        """Find the closest cached identity by centroid distance.

        Args:
            xyxy: Bounding box of the tracked face (x1, y1, x2, y2).
            cached_identities: Mapping of user_id to identity dict.  Each
                dict must contain a ``bbox`` key with [x1, y1, x2, y2].
            max_distance: Maximum centroid distance in pixels for a match.

        Returns:
            Identity dict (with ``user_id`` added) if a match is found
            within *max_distance*, otherwise ``None``.
        """
        if not cached_identities:
            return None

        x1, y1, x2, y2 = xyxy
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0

        best_uid: str | None = None
        best_dist = float("inf")
        best_identity: dict | None = None

        for uid, identity in cached_identities.items():
            bbox = identity.get("bbox")
            if not bbox or len(bbox) < 4:
                continue

            cached_cx = (bbox[0] + bbox[2]) / 2.0
            cached_cy = (bbox[1] + bbox[3]) / 2.0
            dist = math.hypot(cx - cached_cx, cy - cached_cy)

            if dist < best_dist:
                best_dist = dist
                best_uid = uid
                best_identity = identity

        if best_dist <= max_distance and best_uid is not None and best_identity is not None:
            return {
                "user_id": best_uid,
                "name": best_identity.get("name", "Unknown"),
                "student_id": best_identity.get("student_id", ""),
                "confidence": best_identity.get("confidence", 0.0),
            }

        return None

    # ------------------------------------------------------------------
    # Recognition
    # ------------------------------------------------------------------

    def _recognize_new_tracks(self, frame: np.ndarray, tracked: sv.Detections) -> None:
        """Run ArcFace recognition on new/unidentified confirmed tracks.

        First checks the Redis identity cache written by the Attendance Engine.
        If a cached identity matches the track's position (centroid distance
        < 100 px), the cached identity is used and ArcFace is skipped.
        Otherwise, ArcFace recognition is run as a fallback.

        Only processes tracks that are confirmed (3+ consecutive frames) but
        not yet identified.  Recognition is lazy -- once matched, the identity
        is cached and never re-queried unless the track is lost.
        """
        if tracked.tracker_id is None:
            return

        # Read cached identities from attendance engine (cheap sync Redis call)
        cached_identities = self._read_identity_cache()

        for i, track_id in enumerate(tracked.tracker_id):
            tid = int(track_id)
            # Skip already identified or unconfirmed tracks
            if tid in self._identities or tid not in self._confirmed_track_ids:
                continue

            xyxy = tuple(int(v) for v in tracked.xyxy[i])

            # --- Cache-first path: use attendance engine's cached identity ---
            if cached_identities:
                cache_hit = self._match_from_cache(xyxy, cached_identities)
                if cache_hit:
                    self._identities[tid] = cache_hit
                    logger.info(
                        f"[Pipeline:{self.room_id}] Track {tid} -> "
                        f"{cache_hit['name']} (cache, {cache_hit['confidence']:.2f})"
                    )
                    continue

            # --- Fallback: ArcFace recognition ---
            if self._detector is None or self._faiss is None:
                continue

            try:
                x1, y1, x2, y2 = xyxy
                # Pad crop by 20% for better alignment
                bw, bh = x2 - x1, y2 - y1
                pad_x, pad_y = int(bw * 0.2), int(bh * 0.2)
                cx1 = max(0, x1 - pad_x)
                cy1 = max(0, y1 - pad_y)
                cx2 = min(frame.shape[1], x2 + pad_x)
                cy2 = min(frame.shape[0], y2 + pad_y)
                crop = frame[cy1:cy2, cx1:cx2]

                if crop.size == 0:
                    continue

                embedding = self._detector.get_embedding(crop)
                if embedding is None:
                    continue

                match = self._faiss.search_with_margin(
                    embedding,
                    k=settings.RECOGNITION_TOP_K,
                    threshold=settings.RECOGNITION_THRESHOLD,
                    margin=settings.RECOGNITION_MARGIN,
                )
                if match and match.get("user_id") and not match.get("is_ambiguous", False):
                    self._identities[tid] = {
                        "user_id": match["user_id"],
                        "name": match.get("name", "Unknown"),
                        "student_id": match.get("student_id", ""),
                        "confidence": match["confidence"],
                    }
                    logger.info(
                        f"[Pipeline:{self.room_id}] Track {tid} -> "
                        f"{match.get('name')} ({match['confidence']:.2f})"
                    )
            except Exception as e:
                logger.debug(f"[Pipeline:{self.room_id}] Recognition error for track {tid}: {e}")

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def _cleanup_stale_tracks(self, tracked: sv.Detections) -> None:
        """Remove identities and state for tracks no longer active."""
        active_ids: set[int] = set()
        if tracked.tracker_id is not None:
            active_ids = {int(tid) for tid in tracked.tracker_id}

        stale = set(self._track_start_times.keys()) - active_ids
        for tid in stale:
            self._identities.pop(tid, None)
            self._track_start_times.pop(tid, None)
            self._track_frame_counts.pop(tid, None)
            self._confirmed_track_ids.discard(tid)

    def _publish_state_to_redis(self, det_list: list[dict]) -> None:
        """Publish current pipeline state to Redis for FastAPI to read."""
        try:
            identified = [d for d in det_list if d["name"] is not None]
            state = {
                "ts": time.time(),
                "room_id": self.room_id,
                "total_tracks": len(det_list),
                "identified_count": len(identified),
                "identified_users": [
                    {
                        "user_id": self._identities.get(d["track_id"], {}).get("user_id"),
                        "name": d["name"],
                        "confidence": d["confidence"],
                    }
                    for d in identified
                ],
                "status": "running",
            }
            self._redis.set(
                f"pipeline:{self.room_id}:status",
                json.dumps(state),
                ex=30,
            )
            self._redis.set(
                f"pipeline:{self.room_id}:heartbeat",
                json.dumps({"ts": time.time(), "status": "running"}),
                ex=30,
            )
        except Exception as e:
            logger.debug(f"[Pipeline:{self.room_id}] Redis publish error: {e}")

    def _restart_publisher(self) -> None:
        """Restart FFmpeg publisher on failure with retry."""
        if not self._publisher:
            return
        for attempt in range(3):
            try:
                self._publisher.stop()
                time.sleep(1 + attempt)  # increasing backoff
                self._publisher.start()
                logger.info(f"[Pipeline:{self.room_id}] Publisher restarted (attempt {attempt + 1})")
                return
            except Exception as e:
                logger.error(f"[Pipeline:{self.room_id}] Publisher restart attempt {attempt + 1} failed: {e}")
        logger.error(f"[Pipeline:{self.room_id}] Publisher restart failed after 3 attempts")

    def stop(self) -> None:
        """Stop all pipeline components."""
        self._running = False
        logger.info(f"[Pipeline:{self.room_id}] Stopping...")
        if self._reader:
            self._reader.stop()
        if self._publisher:
            self._publisher.stop()

    def update_hud(self, **kwargs) -> None:
        """Update HUD info (called by FastAPI when session state changes).

        Args:
            **kwargs: Key-value pairs matching ``_hud_info`` keys
                (``subject``, ``professor``, ``present_count``, etc.).
        """
        self._hud_info.update(kwargs)
