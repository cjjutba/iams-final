"""
SessionPipeline — real-time processing loop for one active session.

Each active session gets one asyncio.Task running this pipeline:
  FrameGrabber → RealtimeTracker → TrackPresenceService → WebSocket broadcast

At 15fps on M5 MacBook Pro: ~15ms processing per frame, ~50ms headroom.
"""

import asyncio
import base64
import json
import logging
import time
from datetime import datetime

from app.config import settings
from app.services import session_manager
from app.services.frame_grabber import FrameGrabber
from app.services.realtime_tracker import RealtimeTracker
from app.services.track_presence_service import TrackPresenceService
from app.utils.frame_crop import crop_face_with_margin, encode_jpeg

logger = logging.getLogger(__name__)

# Guard against pipeline re-detections firing the same student-facing
# `attendance_event` twice in quick succession. Keyed on
# (user_id, event, attendance_id); values are monotonic seconds.
_ATTENDANCE_EVENT_DEDUP: dict[tuple[str, str, str], float] = {}
_ATTENDANCE_EVENT_DEDUP_WINDOW_SECONDS = 60.0


class SessionPipeline:
    """Real-time processing pipeline for one attendance session.

    Args:
        schedule_id: Schedule UUID for this session.
        grabber: FrameGrabber for the room's RTSP stream.
        db_factory: Callable that returns a new DB session.
        room_id: Room UUID — used by the lifecycle scheduler to decide
            whether a FrameGrabber can be torn down at session end. When
            another active pipeline still references the same room, the
            grabber is kept alive so back-to-back rolling sessions in the
            same classroom transition without a "no frames" gap.
    """

    def __init__(
        self,
        schedule_id: str,
        grabber: FrameGrabber,
        db_factory,
        room_id: str | None = None,
        preview_mode: bool = False,
    ) -> None:
        self.schedule_id = schedule_id
        self.room_id = room_id
        self._grabber = grabber
        self._db_factory = db_factory
        # Preview mode runs face detection + tracking + WS broadcast but skips
        # all presence/attendance state. Used when an admin opens the live
        # page for a schedule that is NOT in its currently-active window, so
        # they still see bounding boxes on the feed without triggering any
        # attendance side-effects (no check-ins, no early-leave events, no DB
        # writes). When the window opens or the admin clicks "Start Session"
        # the preview instance is stopped and a full one takes over.
        self._preview_mode = preview_mode
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._tracker: RealtimeTracker | None = None
        self._presence: TrackPresenceService | None = None
        self._last_flush: float = 0.0
        self._last_summary: float = 0.0
        self._frame_count: int = 0
        self._frame_sequence: int = 0

        # Cached schedule metadata for notification context
        self._faculty_id: str | None = None
        self._subject_code: str | None = None
        self._subject_name: str | None = None

        # Phase-3: dedup key for "captured a live crop for this (user, track)
        # on the warming_up → recognized transition." A fresh ByteTrack ID for
        # the same student (e.g. after they leave and re-enter frame) is a
        # legitimate recapture — (user, track) gives that for free.
        self._recognized_captured: set[tuple[str, int]] = set()

        # Parallel bookkeeping for System Activity RECOGNITION_MISS emits —
        # once per track that commits to recognition_state="unknown" (a
        # registered face isn't matching, or the face simply isn't in the
        # index). Keyed on track_id only because there's no user association.
        self._unknown_emitted: set[int] = set()

    async def start(self) -> None:
        """Initialize services and start the processing loop."""
        from app.models.face_registration import FaceRegistration
        from app.models.room import Room
        from app.models.schedule import Schedule
        from app.models.user import User
        from app.services.ml.faiss_manager import faiss_manager
        from app.services.ml.insightface_model import insightface_model

        db = self._db_factory()
        try:
            if self._preview_mode:
                # Preview mode: no TrackPresenceService. Still cache schedule
                # metadata (for logging context) and build a full name_map from
                # every active face registration so recognized faces render
                # with real names even if they're not enrolled in this class.
                schedule = db.query(Schedule).filter(Schedule.id == self.schedule_id).first()
                if schedule:
                    self._faculty_id = str(schedule.faculty_id)
                    self._subject_code = schedule.subject_code
                    self._subject_name = schedule.subject_name

                full_name_map: dict[str, str] = {}
                face_regs = (
                    db.query(FaceRegistration.user_id, User.first_name, User.last_name)
                    .join(User, FaceRegistration.user_id == User.id)
                    .filter(FaceRegistration.is_active)
                    .all()
                )
                for user_id, first_name, _last_name in face_regs:
                    full_name_map[str(user_id)] = first_name

                preview_camera = None
                if self.room_id:
                    preview_room = db.query(Room).filter(Room.id == self.room_id).first()
                    if preview_room:
                        preview_camera = preview_room.stream_key or preview_room.name

                self._tracker = RealtimeTracker(
                    insightface_model=insightface_model,
                    faiss_manager=faiss_manager,
                    enrolled_user_ids=set(),  # no "enrolled" concept in preview
                    name_map=full_name_map,
                    schedule_id=self.schedule_id,
                    camera_id=preview_camera,
                )

                self._last_flush = time.monotonic()
                self._last_summary = time.monotonic()
            else:
                # Full mode: initialize presence service (short-lived session for setup)
                self._presence = TrackPresenceService(db, self.schedule_id)
                self._presence.start_session()

                # Cache schedule metadata for notification context
                schedule = self._presence._schedule
                if schedule:
                    self._faculty_id = str(schedule.faculty_id)
                    self._subject_code = schedule.subject_code
                    self._subject_name = schedule.subject_name

                # Initialize tracker with enrolled user info
                # Build a complete name_map: enrolled students + all face-registered users.
                # Enrolled names come from presence service; augment with any registered
                # user whose face is in FAISS so recognition always shows a name.
                full_name_map = dict(self._presence.name_map)
                face_regs = (
                    db.query(FaceRegistration.user_id, User.first_name, User.last_name)
                    .join(User, FaceRegistration.user_id == User.id)
                    .filter(FaceRegistration.is_active)
                    .all()
                )
                for user_id, first_name, _last_name in face_regs:
                    uid = str(user_id)
                    if uid not in full_name_map:
                        full_name_map[uid] = first_name

                full_camera = None
                if self.room_id:
                    full_room = db.query(Room).filter(Room.id == self.room_id).first()
                    if full_room:
                        full_camera = full_room.stream_key or full_room.name

                self._tracker = RealtimeTracker(
                    insightface_model=insightface_model,
                    faiss_manager=faiss_manager,
                    enrolled_user_ids=self._presence.enrolled_ids,
                    name_map=full_name_map,
                    schedule_id=self.schedule_id,
                    camera_id=full_camera,
                )

                self._last_flush = time.monotonic()
                self._last_summary = time.monotonic()

        finally:
            # Close the setup session immediately — loop creates short-lived sessions
            db.close()

        # Start the async loop (no long-lived DB session)
        task_name = (
            f"preview-{self.schedule_id[:8]}" if self._preview_mode else f"pipeline-{self.schedule_id[:8]}"
        )
        self._task = asyncio.create_task(self._run_loop(), name=task_name)

        # In full mode, register in the global session manager so API endpoints
        # see session_active=True. Preview pipelines do NOT register — their
        # presence must not affect the `/presence/sessions/active` surface.
        if not self._preview_mode:
            session_manager.register_session(
                self.schedule_id,
                {
                    "subject_code": self._subject_code,
                    "subject_name": self._subject_name,
                    "student_count": len(self._presence.enrolled_ids) if self._presence else 0,
                },
            )

        logger.info(
            "SessionPipeline started for schedule %s (preview=%s)",
            self.schedule_id,
            self._preview_mode,
        )

    async def stop(self) -> dict:
        """Stop the pipeline and return session summary."""
        self._stop_event.set()

        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (TimeoutError, asyncio.CancelledError):
                self._task.cancel()

        summary: dict = {}
        if self._presence is not None:
            db = self._db_factory()
            try:
                self._presence.rebind_db(db)
                summary = self._presence.end_session()
            finally:
                db.close()

        if self._tracker is not None:
            self._tracker.reset()

        # Only unregister from the global session manager if we registered.
        # Preview pipelines never register, so skip to avoid removing a real
        # session that may have started in parallel.
        if not self._preview_mode:
            session_manager.unregister_session(self.schedule_id)

        logger.info(
            "SessionPipeline stopped for schedule %s (preview=%s)",
            self.schedule_id,
            self._preview_mode,
        )
        return summary

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def update_early_leave_timeout(self, timeout_seconds: float) -> None:
        """Update the early leave timeout on the running presence service."""
        if self._presence is not None:
            self._presence.set_early_leave_timeout(timeout_seconds)
            logger.info(
                "Early leave timeout updated to %.0fs for schedule %s",
                timeout_seconds,
                self.schedule_id[:8],
            )

    async def _run_loop(self) -> None:
        """Main processing loop — runs at PROCESSING_FPS.

        DB sessions are created short-lived for flush/write operations only.
        The main frame-processing loop stays lightweight with no held connections.
        """
        frame_interval = 1.0 / settings.PROCESSING_FPS
        loop = asyncio.get_event_loop()
        _consecutive_none = 0

        try:
            while not self._stop_event.is_set():
                loop_start = time.monotonic()

                try:
                    # ``grab_with_pts`` returns ``(frame, rtp_pts_90k)`` so
                    # the broadcaster can ship the upstream RTP timestamp
                    # to the admin overlay for video-aligned rendering
                    # (live-feed plan 2026-04-25 Step 3).
                    grabbed = self._grabber.grab_with_pts()
                    if grabbed is None:
                        frame = None
                        rtp_pts_90k: int | None = None
                    else:
                        frame, rtp_pts_90k = grabbed
                    if frame is None:
                        _consecutive_none += 1
                        # Pause presence tracking after ~2s of missing frames so
                        # camera downtime does NOT count as student absence.
                        # resume_absence_tracking() fires automatically on next frame.
                        if _consecutive_none == int(2.0 * settings.PROCESSING_FPS):
                            if self._presence is not None:
                                self._presence.pause_absence_tracking(time.monotonic())
                        # Log every 10s worth of missed frames (at PROCESSING_FPS)
                        if _consecutive_none == int(10 * settings.PROCESSING_FPS):
                            logger.warning(
                                "Pipeline %s: no frames for ~10s — camera may be offline",
                                self.schedule_id[:8],
                            )
                        elif _consecutive_none % int(60 * settings.PROCESSING_FPS) == 0:
                            logger.warning(
                                "Pipeline %s: no frames for ~%ds — camera offline",
                                self.schedule_id[:8],
                                _consecutive_none // int(settings.PROCESSING_FPS),
                            )
                    if frame is not None:
                        _consecutive_none = 0
                        # Run CPU-intensive ML work in thread executor.
                        # ``rtp_pts_90k`` is propagated through the tracker
                        # onto ``TrackFrame`` so the broadcaster can ship
                        # it to the admin overlay (live-feed plan Step 3).
                        track_frame = await loop.run_in_executor(
                            None, self._tracker.process, frame, rtp_pts_90k
                        )

                        self._frame_count += 1

                        # Broadcast frame update FIRST — minimizes latency to phone.
                        # This is the ONLY side-effect the preview pipeline produces.
                        await self._broadcast_frame_update(track_frame)

                        # Phase-3: on the warming_up → recognized transition for
                        # each (user, track) pair, capture a server-side crop
                        # to Redis so the admin face-comparison sheet can show
                        # the exact frame the ML saw. No-op in preview mode or
                        # when ENABLE_REDIS is false.
                        if not self._preview_mode:
                            self._capture_newly_recognized_crops(frame, track_frame)
                            # Emit RECOGNITION_MISS once per track that commits
                            # to recognition_state="unknown". This is the tri-
                            # state gating described in config.py — once a track
                            # has had UNKNOWN_CONFIRM_ATTEMPTS low-score reads
                            # the RealtimeTracker flips it to "unknown".
                            for t in track_frame.tracks:
                                if (
                                    t.recognition_state == "unknown"
                                    and t.track_id not in self._unknown_emitted
                                ):
                                    self._unknown_emitted.add(t.track_id)
                                    self._emit_recognition_miss(t)

                        if not self._preview_mode:
                            # Update presence state — use short-lived DB session for
                            # any event-driven writes (check-in, early leave)
                            db = self._db_factory()
                            try:
                                self._presence.rebind_db(db)
                                events = self._presence.process_track_frame(track_frame, time.monotonic())
                            finally:
                                db.close()

                            # Handle events (check-in notifications, early leave alerts)
                            if events:
                                # Broadcast updated summary immediately on any status change
                                await self._broadcast_attendance_summary()
                                self._last_summary = time.monotonic()
                            for event in events:
                                await self._handle_event(event)

                        # Log performance periodically
                        if self._frame_count % 100 == 0:
                            logger.info(
                                "Pipeline %s: %d frames, %.1fms/frame, %d tracks",
                                self.schedule_id[:8],
                                self._frame_count,
                                track_frame.processing_ms,
                                len(track_frame.tracks),
                            )

                except asyncio.CancelledError:
                    raise  # Re-raise cancellation
                except Exception:
                    # Log but don't crash — keep pipeline running for next frame
                    logger.exception("Pipeline %s: error processing frame %d", self.schedule_id[:8], self._frame_count)

                # Periodic flush (every PRESENCE_FLUSH_INTERVAL) — short-lived DB session
                now = time.monotonic()
                if not self._preview_mode and (now - self._last_flush) >= settings.PRESENCE_FLUSH_INTERVAL:
                    try:
                        db = self._db_factory()
                        try:
                            self._presence.rebind_db(db)
                            self._presence.flush_presence_logs()
                        finally:
                            db.close()
                    except Exception:
                        logger.exception("Pipeline %s: error flushing presence", self.schedule_id[:8])
                    self._last_flush = now

                # Periodic attendance summary (every 2s for real-time UI responsiveness).
                # Preview mode skips the attendance summary broadcast (there's
                # nothing to summarise) but still emits stream_status so the UI
                # can surface camera-offline state.
                if (now - self._last_summary) >= 2.0:
                    if not self._preview_mode:
                        await self._broadcast_attendance_summary()
                    # Broadcast stream health so the app can show "camera offline"
                    await self._broadcast_stream_status(_consecutive_none > 0)
                    self._last_summary = now

                # Sleep to hit target FPS
                elapsed = time.monotonic() - loop_start
                if elapsed > frame_interval * 1.5:
                    logger.debug(
                        "Pipeline %s: frame took %.1fms (budget %.1fms), skipping ahead",
                        self.schedule_id[:8],
                        elapsed * 1000,
                        frame_interval * 1000,
                    )
                sleep_time = max(0, frame_interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.info("Pipeline %s cancelled", self.schedule_id[:8])
        except Exception:
            logger.exception("Pipeline %s crashed", self.schedule_id[:8])

    async def _broadcast_frame_update(self, track_frame) -> None:
        """Send frame_update message to WebSocket clients."""
        self._frame_sequence += 1
        try:
            from app.routers.websocket import ws_manager

            tracks_data = [
                {
                    "track_id": t.track_id,
                    "bbox": t.bbox,
                    "velocity": t.velocity,
                    "name": t.name,
                    "confidence": t.confidence,
                    "user_id": t.user_id,
                    "status": t.status,
                    # Tri-state signal consumed by the phone overlay. "warming_up"
                    # renders as "Detecting…" (orange) instead of a misleading red
                    # "Unknown" while FAISS works through the warm-up window.
                    "recognition_state": t.recognition_state,
                    "is_active": True,  # All broadcast tracks are currently active
                }
                for t in track_frame.tracks
            ]

            # Per-stage timing breakdown for the live HUD. ``other_ms`` is
            # everything outside the three named stages (NMS, ByteTrack
            # update, identity-cache bookkeeping, dedup, expiry). When
            # ``other_ms`` dominates, the bottleneck has moved off ML and
            # into the rest of the loop — a different debugging path than
            # the SCRFD/ArcFace optimisations in Step 2b of the
            # 2026-04-25 live-feed plan.
            det_ms = round(track_frame.det_ms, 1)
            embed_ms = round(track_frame.embed_ms, 1)
            faiss_ms = round(track_frame.faiss_ms, 1)
            other_ms = round(
                max(0.0, track_frame.processing_ms - track_frame.det_ms - track_frame.embed_ms - track_frame.faiss_ms),
                1,
            )

            payload = {
                "type": "frame_update",
                "timestamp": track_frame.timestamp,
                "server_time_ms": int(time.time() * 1000),
                "frame_sequence": self._frame_sequence,
                "frame_size": [settings.FRAME_GRABBER_WIDTH, settings.FRAME_GRABBER_HEIGHT],
                "tracks": tracks_data,
                "fps": round(track_frame.fps, 1),
                "processing_ms": round(track_frame.processing_ms, 1),
                "det_ms": det_ms,
                "embed_ms": embed_ms,
                "faiss_ms": faiss_ms,
                "other_ms": other_ms,
            }
            # Upstream RTP 90 kHz timestamp of the source RTSP frame this
            # update describes. Only emitted when the FrameGrabber
            # captured it; consumed by the admin overlay's frame-aligner
            # to draw bboxes on the matching ``requestVideoFrameCallback``
            # video frame. See live-feed plan 2026-04-25 Step 3.
            if track_frame.rtp_pts_90k is not None:
                payload["rtp_pts_90k"] = int(track_frame.rtp_pts_90k)

            await ws_manager.broadcast_attendance(self.schedule_id, payload)
        except Exception:
            logger.debug("Frame update broadcast failed", exc_info=True)

    def _capture_newly_recognized_crops(self, frame, track_frame) -> None:
        """Fan out async crop-save tasks for any track that just became recognized.

        Runs on the pipeline thread and returns immediately — per-track work
        is dispatched to the default thread executor via ``_save_live_crop``
        so neither SCRFD+ArcFace nor the frame broadcaster wait on JPEG
        encode / Redis round-trips.

        Guarded upstream by ``not self._preview_mode`` (see call site). Each
        ``_save_live_crop`` also guards on ``settings.ENABLE_REDIS`` as a
        belt-and-braces no-op for VPS misconfigs.
        """
        if not settings.ENABLE_REDIS or frame is None:
            return

        # Frame-buffer aliasing defense: if FrameGrabber ever starts recycling
        # buffers, crops dispatched to the executor could see mutated pixels
        # for subsequent frames. ``frame.copy()`` is ~2 ms for a 1280×720 BGR
        # array — cheap insurance, only paid when we actually have something
        # to capture.
        fresh_copy = None

        for t in track_frame.tracks:
            if t.recognition_state != "recognized":
                continue
            if not t.user_id or not t.is_active:
                continue
            key = (t.user_id, t.track_id)
            if key in self._recognized_captured:
                continue
            self._recognized_captured.add(key)

            # Emit System Activity RECOGNITION_MATCH once per tracker
            # identity transition. Cardinality is gated by the set above —
            # one event per (user, track), not per frame. A short-lived DB
            # session is cheap because transitions are rare.
            self._emit_recognition_match(t)

            if fresh_copy is None:
                try:
                    fresh_copy = frame.copy()
                except Exception:
                    logger.debug("frame.copy() failed, skipping live-crop batch", exc_info=True)
                    # Re-add keys so the next frame can try again.
                    self._recognized_captured.discard(key)
                    return

            asyncio.create_task(self._save_live_crop(fresh_copy, t))

    async def _save_live_crop(self, frame, track) -> None:
        """Crop, encode, and LPUSH a JPEG into the per-user Redis ring buffer.

        Key scheme: ``live_crops:{schedule_id}:{user_id}`` as a Redis LIST,
        newest-first. LTRIM caps depth at 10. EXPIRE refreshes TTL to 2h on
        every write so inactive keys self-clean.
        """
        if not settings.ENABLE_REDIS:
            return
        try:
            loop = asyncio.get_event_loop()

            def _encode() -> bytes | None:
                crop = crop_face_with_margin(frame, track.bbox)
                return encode_jpeg(crop)

            jpeg_bytes = await loop.run_in_executor(None, _encode)
            if not jpeg_bytes:
                return

            entry = {
                "crop_b64": base64.b64encode(jpeg_bytes).decode("ascii"),
                "captured_at": datetime.now().isoformat(),
                "confidence": float(track.confidence),
                "track_id": int(track.track_id),
                "bbox": [float(v) for v in track.bbox],
            }

            from app.redis_client import get_redis

            r = await get_redis()
            if r is None:
                return

            key = f"live_crops:{self.schedule_id}:{track.user_id}"
            async with r.pipeline(transaction=False) as pipe:
                pipe.lpush(key, json.dumps(entry).encode("utf-8"))
                pipe.ltrim(key, 0, 9)
                pipe.expire(key, 7200)
                await pipe.execute()

            logger.info(
                "Captured live crop for user=%s track_id=%s schedule=%s",
                track.user_id,
                track.track_id,
                self.schedule_id[:8],
            )
        except Exception:
            logger.debug(
                "live crop save failed for user=%s track_id=%s",
                getattr(track, "user_id", "?"),
                getattr(track, "track_id", "?"),
                exc_info=True,
            )

    def _emit_recognition_match(self, track) -> None:
        """Emit a System Activity RECOGNITION_MATCH event.

        Fired once per tracker identity transition (first time a given
        (user_id, track_id) pair commits to ``recognition_state=recognized``).
        Runs on the pipeline thread — uses a short-lived DB session and
        swallows all failures so the ML loop never stalls on activity log
        writes.
        """
        if self._preview_mode:
            return
        try:
            from app.services.activity_service import (
                EventType,
                emit_recognition_transition,
            )

            db = self._db_factory()
            try:
                # camera_id here is a best-effort handle — the true
                # short-name (e.g. "eb226") is owned by the FrameGrabber
                # and not plumbed through. Room UUID is still useful for
                # filtering in the admin activity feed.
                camera_handle = self.room_id
                emit_recognition_transition(
                    db,
                    event_type=EventType.RECOGNITION_MATCH,
                    summary=(
                        f"Recognition match: user={track.user_id} "
                        f"track={track.track_id} "
                        f"confidence={float(track.confidence):.2f}"
                    ),
                    schedule_id=self.schedule_id,
                    camera_id=camera_handle,
                    student_id=str(track.user_id) if track.user_id else None,
                    payload={
                        "track_id": int(track.track_id),
                        "confidence": float(track.confidence),
                        "subject_code": self._subject_code,
                    },
                    autocommit=True,
                )
            finally:
                db.close()
        except Exception:
            logger.debug("RECOGNITION_MATCH emit failed", exc_info=True)

    def _emit_recognition_miss(self, track) -> None:
        """Emit a System Activity RECOGNITION_MISS event.

        Fired once per track that commits to ``recognition_state=unknown``
        — a face detected but not matched to any registered identity.
        Cardinality gated by ``self._unknown_emitted``.
        """
        if self._preview_mode:
            return
        try:
            from app.services.activity_service import (
                EventSeverity,
                EventType,
                emit_recognition_transition,
            )

            db = self._db_factory()
            try:
                # camera_id here is a best-effort handle — the true
                # short-name (e.g. "eb226") is owned by the FrameGrabber
                # and not plumbed through. Room UUID is still useful for
                # filtering in the admin activity feed.
                camera_handle = self.room_id
                emit_recognition_transition(
                    db,
                    event_type=EventType.RECOGNITION_MISS,
                    summary=(
                        f"Unknown face committed: track={track.track_id}"
                    ),
                    schedule_id=self.schedule_id,
                    camera_id=camera_handle,
                    student_id=None,
                    severity=EventSeverity.INFO,
                    payload={
                        "track_id": int(track.track_id),
                        "subject_code": self._subject_code,
                    },
                    autocommit=True,
                )
            finally:
                db.close()
        except Exception:
            logger.debug("RECOGNITION_MISS emit failed", exc_info=True)

    async def _broadcast_stream_status(self, frames_missing: bool) -> None:
        """Notify clients whether the camera stream is healthy."""
        try:
            from app.routers.websocket import ws_manager

            await ws_manager.broadcast_attendance(
                self.schedule_id,
                {
                    "type": "stream_status",
                    "camera_online": not frames_missing,
                    "grabber_alive": self._grabber.is_alive() if self._grabber else False,
                },
            )
        except Exception:
            pass

    async def _broadcast_attendance_summary(self) -> None:
        """Send periodic attendance_summary message to WebSocket clients."""
        if self._presence is None:
            return
        try:
            from app.routers.websocket import ws_manager

            summary = self._presence.get_attendance_summary()
            await ws_manager.broadcast_attendance(self.schedule_id, summary)
        except Exception:
            logger.debug("Attendance summary broadcast failed", exc_info=True)

    async def _handle_event(self, event: dict) -> None:
        """Process presence events (check-in, early leave, return)."""
        event_type = event.get("event")
        try:
            from app.routers.websocket import ws_manager

            if event_type == "check_in":
                await ws_manager.broadcast_attendance(
                    self.schedule_id,
                    {
                        "type": "check_in",
                        "schedule_id": self.schedule_id,
                        **event,
                    },
                )

            elif event_type == "early_leave":
                await ws_manager.broadcast_attendance(
                    self.schedule_id,
                    {
                        "type": "early_leave",
                        "schedule_id": self.schedule_id,
                        **event,
                    },
                )

            elif event_type == "early_leave_return":
                await ws_manager.broadcast_attendance(
                    self.schedule_id,
                    {
                        "type": "early_leave_return",
                        "schedule_id": self.schedule_id,
                        **event,
                    },
                )

            # Fan out a student-facing `attendance_event` on the per-user
            # alert channel. This is what drives the Kotlin student app's
            # real-time UI without needing a per-schedule subscription.
            await self._broadcast_student_attendance_event(event_type, event)

        except Exception:
            logger.debug("Event broadcast failed: %s", event_type, exc_info=True)

        # Send in-app / email notifications (fire-and-forget, never breaks pipeline)
        await self._send_event_notifications(event)

    async def _broadcast_student_attendance_event(
        self,
        event_type: str | None,
        event: dict,
    ) -> None:
        """Mirror a check_in/early_leave/early_leave_return onto the affected
        student's `/ws/alerts/{user_id}` channel so the student app gets a
        live state-change event without subscribing to the per-schedule
        firehose.

        Dedup key: (student_id, event_type, attendance_id). A 60s window
        survives transient re-detections (the pipeline may flip the same
        track on/off across a few frames before ByteTrack stabilises it).
        """
        if event_type not in {"check_in", "early_leave", "early_leave_return"}:
            return

        student_id = event.get("student_id")
        if not student_id:
            return

        attendance_id = event.get("attendance_id")
        if not attendance_id:
            # Without attendance_id we can't correlate on the client, so skip.
            return

        dedup_key = (str(student_id), event_type, str(attendance_id))
        now_mono = time.monotonic()
        last = _ATTENDANCE_EVENT_DEDUP.get(dedup_key)
        if last is not None and (now_mono - last) < _ATTENDANCE_EVENT_DEDUP_WINDOW_SECONDS:
            return
        _ATTENDANCE_EVENT_DEDUP[dedup_key] = now_mono

        # Opportunistic prune to keep the dict bounded.
        if len(_ATTENDANCE_EVENT_DEDUP) > 512:
            cutoff = now_mono - _ATTENDANCE_EVENT_DEDUP_WINDOW_SECONDS
            for k, v in list(_ATTENDANCE_EVENT_DEDUP.items()):
                if v < cutoff:
                    _ATTENDANCE_EVENT_DEDUP.pop(k, None)

        if event_type == "check_in":
            status_value = event.get("status")
            check_in_time = event.get("check_in_time")
        elif event_type == "early_leave":
            status_value = "early_leave"
            check_in_time = event.get("check_in_time")
        else:  # early_leave_return
            status_value = event.get("restored_status")
            check_in_time = event.get("returned_at")

        payload = {
            "type": "attendance_event",
            "event": event_type,
            "schedule_id": self.schedule_id,
            "attendance_id": str(attendance_id),
            "student_id": str(student_id),
            "status": status_value,
            "check_in_time": check_in_time,
            "subject_code": self._subject_code,
            "subject_name": self._subject_name,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            from app.routers.websocket import ws_manager

            await ws_manager.broadcast_alert(str(student_id), payload)
        except Exception:
            logger.debug(
                "attendance_event broadcast failed: %s / %s",
                event_type,
                student_id,
                exc_info=True,
            )

    async def _send_event_notifications(self, event: dict) -> None:
        """Send in-app and email notifications for pipeline events.

        Opens a short-lived DB session, calls notification_service.notify(),
        and always closes the session. Failures are logged but never propagated
        so the pipeline keeps running.
        """
        event_type = event.get("event")
        if not event_type:
            return

        db = self._db_factory()
        try:
            from app.services.notification_service import notify as _notify

            subject_code = self._subject_code or "class"

            if event_type == "check_in":
                student_id = event.get("student_id")
                if student_id:
                    await _notify(
                        db,
                        student_id,
                        "Attendance Confirmed",
                        f"You are marked {event.get('status', 'present')} for {subject_code}.",
                        "check_in",
                        preference_key="attendance_confirmation",
                        toast_type="success",
                        send_email=True,
                        email_template="check_in",
                        email_context={
                            "student_name": event.get("student_name", ""),
                            "subject_code": subject_code,
                            "subject_name": self._subject_name or "",
                            "status": event.get("status", "present"),
                            "check_in_time": event.get("check_in_time", ""),
                        },
                    )

            elif event_type == "early_leave":
                student_id = event.get("student_id")
                student_name = event.get("student_name", "A student")
                attendance_id = event.get("attendance_id")
                absent_seconds = event.get("absent_seconds", 0)
                consecutive_misses = max(1, int(absent_seconds / settings.SCAN_INTERVAL_SECONDS))

                # Faculty notification
                if self._faculty_id:
                    await _notify(
                        db,
                        self._faculty_id,
                        "Early Leave Detected",
                        f"{student_name} left {subject_code} early.",
                        "early_leave",
                        preference_key="early_leave_alerts",
                        toast_type="warning",
                        send_email=True,
                        email_template="early_leave",
                        email_context={
                            "student_name": student_name,
                            "subject_code": subject_code,
                            "consecutive_misses": consecutive_misses,
                            "last_seen_at": event.get("check_in_time", "N/A"),
                            "severity": "auto_detected",
                        },
                        reference_id=attendance_id,
                        reference_type="early_leave",
                        # Dedup per (user, attendance row): guards against
                        # transient pipeline re-detections firing the alert twice.
                        dedup_window_seconds=300,
                    )

                # Student notification
                if student_id:
                    await _notify(
                        db,
                        student_id,
                        "Early Leave Recorded",
                        f"You were marked as early leave from {subject_code}.",
                        "early_leave",
                        preference_key="early_leave_alerts",
                        toast_type="warning",
                        send_email=True,
                        email_template="early_leave",
                        email_context={
                            "student_name": student_name,
                            "subject_code": subject_code,
                            "consecutive_misses": consecutive_misses,
                            "last_seen_at": event.get("check_in_time", "N/A"),
                            "severity": "auto_detected",
                        },
                        reference_id=attendance_id,
                        reference_type="early_leave",
                        dedup_window_seconds=300,
                    )

            elif event_type == "early_leave_return":
                student_id = event.get("student_id")
                student_name = event.get("student_name", "A student")

                # Faculty notification (no email — low urgency)
                if self._faculty_id:
                    await _notify(
                        db,
                        self._faculty_id,
                        "Student Returned",
                        f"{student_name} has returned to {subject_code}.",
                        "early_leave_return",
                        toast_type="info",
                    )

                # Student notification (no email)
                if student_id:
                    await _notify(
                        db,
                        student_id,
                        "Return Noted",
                        f"Your return to {subject_code} has been recorded.",
                        "early_leave_return",
                        toast_type="info",
                    )

        except Exception:
            logger.warning(
                "Failed to send event notifications for %s (schedule %s)",
                event_type,
                self.schedule_id[:8],
                exc_info=True,
            )
        finally:
            db.close()
