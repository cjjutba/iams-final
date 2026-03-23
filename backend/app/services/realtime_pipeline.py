"""
SessionPipeline — real-time processing loop for one active session.

Each active session gets one asyncio.Task running this pipeline:
  FrameGrabber → RealtimeTracker → TrackPresenceService → WebSocket broadcast

At 10fps on M5 MacBook Pro: ~15ms processing per frame, 85ms headroom.
"""

import asyncio
import logging
import time

from sqlalchemy.orm import Session

from app.config import settings
from app.services.frame_grabber import FrameGrabber
from app.services.realtime_tracker import RealtimeTracker
from app.services.track_presence_service import TrackPresenceService

logger = logging.getLogger(__name__)


class SessionPipeline:
    """Real-time processing pipeline for one attendance session.

    Args:
        schedule_id: Schedule UUID for this session.
        grabber: FrameGrabber for the room's RTSP stream.
        db_factory: Callable that returns a new DB session.
    """

    def __init__(
        self,
        schedule_id: str,
        grabber: FrameGrabber,
        db_factory,
    ) -> None:
        self.schedule_id = schedule_id
        self._grabber = grabber
        self._db_factory = db_factory
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._tracker: RealtimeTracker | None = None
        self._presence: TrackPresenceService | None = None
        self._last_flush: float = 0.0
        self._last_summary: float = 0.0
        self._frame_count: int = 0

    async def start(self) -> None:
        """Initialize services and start the processing loop."""
        db = self._db_factory()
        try:
            # Initialize presence service
            self._presence = TrackPresenceService(db, self.schedule_id)
            self._presence.start_session()

            # Initialize tracker with enrolled user info
            from app.services.ml.faiss_manager import faiss_manager
            from app.services.ml.insightface_model import insightface_model

            # Build a complete name_map: enrolled students + all face-registered users.
            # Enrolled names come from presence service; augment with any registered
            # user whose face is in FAISS so recognition always shows a name.
            from app.models.face_registration import FaceRegistration
            from app.models.user import User

            full_name_map = dict(self._presence.name_map)
            face_regs = (
                db.query(FaceRegistration.user_id, User.first_name, User.last_name)
                .join(User, FaceRegistration.user_id == User.id)
                .filter(FaceRegistration.is_active)
                .all()
            )
            for user_id, first_name, last_name in face_regs:
                uid = str(user_id)
                if uid not in full_name_map:
                    full_name_map[uid] = f"{first_name} {last_name}"

            self._tracker = RealtimeTracker(
                insightface_model=insightface_model,
                faiss_manager=faiss_manager,
                enrolled_user_ids=self._presence.enrolled_ids,
                name_map=full_name_map,
            )

            self._last_flush = time.monotonic()
            self._last_summary = time.monotonic()

            # Start the async loop
            self._task = asyncio.create_task(
                self._run_loop(db), name=f"pipeline-{self.schedule_id[:8]}"
            )
            logger.info("SessionPipeline started for schedule %s", self.schedule_id)

        except Exception:
            db.close()
            raise

    async def stop(self) -> dict:
        """Stop the pipeline and return session summary."""
        self._stop_event.set()

        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()

        summary = {}
        if self._presence is not None:
            summary = self._presence.end_session()

        if self._tracker is not None:
            self._tracker.reset()

        logger.info("SessionPipeline stopped for schedule %s", self.schedule_id)
        return summary

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _run_loop(self, db: Session) -> None:
        """Main processing loop — runs at PROCESSING_FPS."""
        frame_interval = 1.0 / settings.PROCESSING_FPS
        loop = asyncio.get_event_loop()

        try:
            while not self._stop_event.is_set():
                loop_start = time.monotonic()

                frame = self._grabber.grab()
                if frame is not None:
                    # Run CPU-intensive ML work in thread executor
                    track_frame = await loop.run_in_executor(
                        None, self._tracker.process, frame
                    )

                    self._frame_count += 1

                    # Update presence state
                    events = self._presence.process_track_frame(
                        track_frame, time.monotonic()
                    )

                    # Broadcast frame update via WebSocket
                    await self._broadcast_frame_update(track_frame)

                    # Handle events (check-in notifications, early leave alerts)
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

                # Periodic flush (every PRESENCE_FLUSH_INTERVAL)
                now = time.monotonic()
                if (now - self._last_flush) >= settings.PRESENCE_FLUSH_INTERVAL:
                    self._presence.flush_presence_logs()
                    self._last_flush = now

                # Periodic attendance summary (every 5s)
                if (now - self._last_summary) >= 5.0:
                    await self._broadcast_attendance_summary()
                    self._last_summary = now

                # Sleep to hit target FPS
                elapsed = time.monotonic() - loop_start
                sleep_time = max(0, frame_interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.info("Pipeline %s cancelled", self.schedule_id[:8])
        except Exception:
            logger.exception("Pipeline %s crashed", self.schedule_id[:8])
        finally:
            db.close()

    async def _broadcast_frame_update(self, track_frame) -> None:
        """Send frame_update message to WebSocket clients."""
        try:
            from app.routers.websocket import ws_manager

            tracks_data = [
                {
                    "track_id": t.track_id,
                    "bbox": t.bbox,
                    "name": t.name,
                    "confidence": t.confidence,
                    "user_id": t.user_id,
                    "status": t.status,
                }
                for t in track_frame.tracks
            ]

            await ws_manager.broadcast_attendance(self.schedule_id, {
                "type": "frame_update",
                "timestamp": track_frame.timestamp,
                "tracks": tracks_data,
                "fps": round(track_frame.fps, 1),
                "processing_ms": round(track_frame.processing_ms, 1),
            })
        except Exception:
            logger.debug("Frame update broadcast failed", exc_info=True)

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
                await ws_manager.broadcast_attendance(self.schedule_id, {
                    "type": "check_in",
                    "schedule_id": self.schedule_id,
                    **event,
                })

            elif event_type == "early_leave":
                await ws_manager.broadcast_attendance(self.schedule_id, {
                    "type": "early_leave",
                    "schedule_id": self.schedule_id,
                    **event,
                })

                # Also send to alert channel for faculty/student
                # (handled by the old PresenceService notification system)

            elif event_type == "early_leave_return":
                await ws_manager.broadcast_attendance(self.schedule_id, {
                    "type": "early_leave_return",
                    "schedule_id": self.schedule_id,
                    **event,
                })

        except Exception:
            logger.debug("Event broadcast failed: %s", event_type, exc_info=True)
