"""
IAMS Edge Device Main Application

Raspberry Pi edge device for continuous face detection and attendance monitoring.

Architecture:
- Camera capture loop (15 FPS)
- MediaPipe face detection
- Face cropping and JPEG encoding
- HTTP transmission to backend
- Offline queue with retry logic

Usage:
    python -m app.main

Signals:
    SIGTERM, SIGINT: Graceful shutdown
"""

import signal
import sys
import time
import asyncio
from datetime import datetime
from typing import Optional

from app.config import config, logger
from app.camera import CameraManager
from app.detector import FaceDetector
from app.processor import FaceProcessor
from app.sender import SyncBackendSender
from app.queue_manager import QueueManager, RetryWorker
from app.stream_relay import stream_relay


class EdgeDevice:
    """
    Main edge device application.

    Coordinates camera, detector, processor, sender, and queue manager.
    """

    def __init__(self):
        # Components
        self.camera = CameraManager()
        self.detector = FaceDetector()
        self.processor = FaceProcessor()
        self.sender = SyncBackendSender()
        self.queue_manager = QueueManager()
        self.retry_worker: Optional[RetryWorker] = None

        # State
        self.is_running = False
        self.scan_count = 0
        self.total_faces_detected = 0
        self.total_faces_sent = 0

        # Session awareness state
        self._session_active = False
        self._current_schedule_id: Optional[str] = None

        # Configuration
        self.room_id = config.ROOM_ID
        self.scan_interval = config.SCAN_INTERVAL
        self.session_aware = config.SESSION_AWARE
        self.session_poll_interval = config.SESSION_POLL_INTERVAL

        # Stream relay
        self.stream_relay_enabled = config.STREAM_RELAY_ENABLED

    def initialize(self) -> bool:
        """
        Initialize all components.

        Returns:
            True if all components initialized successfully
        """
        logger.info("Initializing IAMS Edge Device...")
        logger.info(f"Room ID: {self.room_id}")
        logger.info(f"Backend URL: {config.BACKEND_URL}")
        logger.info(f"Scan interval: {self.scan_interval}s")
        logger.info(f"Session-aware: {self.session_aware}")
        if self.session_aware:
            logger.info(f"Session poll interval: {self.session_poll_interval}s")

        # Validate configuration
        try:
            config.validate()
        except ValueError as e:
            logger.error(f"Configuration validation failed: {e}")
            return False

        # Initialize camera
        if not self.camera.initialize():
            logger.error("Failed to initialize camera")
            return False

        # Initialize detector
        if not self.detector.initialize():
            logger.error("Failed to initialize face detector")
            self.camera.stop()
            return False

        # Start retry worker
        self.retry_worker = RetryWorker(self.queue_manager, self.sender)
        self.retry_worker.start()

        logger.info("All components initialized successfully")
        return True

    def shutdown(self) -> None:
        """
        Gracefully shutdown all components.
        """
        logger.info("Shutting down edge device...")

        self.is_running = False

        # Stop stream relay (safe to call even if never started)
        stream_relay.stop()

        # Stop retry worker
        if self.retry_worker:
            self.retry_worker.stop()

        # Close detector
        self.detector.close()

        # Stop camera
        self.camera.stop()

        # Close HTTP client
        self.sender.close()

        # Log final statistics
        self._log_statistics()

        logger.info("Edge device shutdown complete")

    def _check_session(self) -> bool:
        """
        Check if there is an active session for this room.

        Updates internal session state. When session awareness is disabled,
        always returns True (scan proceeds unconditionally).

        Returns:
            True if scanning should proceed, False if no active session
        """
        if not self.session_aware:
            return True

        try:
            active, schedule_id = self.sender.check_session_status(self.room_id)
        except Exception as e:
            logger.warning(f"Failed to check session status: {e}")
            # On error, fall back to previous known state.
            # If we have never had a session, skip. If we had one, keep scanning
            # to avoid missing attendance during transient network issues.
            if self._session_active:
                logger.info("Continuing with previously active session due to check failure")
                return True
            return False

        prev_active = self._session_active
        self._session_active = active
        self._current_schedule_id = schedule_id

        # Log transitions
        if active and not prev_active:
            logger.info(f"Session became active (schedule_id={schedule_id}), starting scans")
        elif not active and prev_active:
            logger.info("Session ended, pausing scans")

        # Start/stop stream relay on session transitions
        if self.stream_relay_enabled:
            if active and not prev_active:
                stream_relay.start(self.room_id)
            elif not active and prev_active:
                stream_relay.stop()

        return active

    def run_single_scan(self) -> bool:
        """
        Execute a single scan cycle.

        Pipeline:
        1. Check for active session (if session-aware)
        2. Capture frame from camera
        3. Detect faces in frame
        4. Crop and process each face
        5. Send to backend (or queue if offline)

        Returns:
            True if a scan was performed, False if skipped (no active session)
        """
        # Check session status before scanning
        if not self._check_session():
            logger.debug("No active session for this room, skipping scan")
            return False

        scan_start = time.time()
        scan_timestamp = datetime.utcnow()

        logger.info(f"Starting scan #{self.scan_count + 1}...")

        # Capture frame
        frame = self.camera.capture_frame()
        if frame is None:
            logger.warning("Failed to capture frame, skipping scan")
            return True

        # Detect faces
        face_boxes = self.detector.detect(frame)
        face_count = len(face_boxes)

        self.total_faces_detected += face_count

        logger.info(f"Detected {face_count} faces")

        if face_count == 0:
            logger.info("No faces detected, skipping transmission")
            self.scan_count += 1
            return True

        # Process faces
        face_data_list = self.processor.process_batch(frame, face_boxes)

        if not face_data_list:
            logger.warning("No faces successfully processed")
            self.scan_count += 1
            return True

        logger.info(f"Processed {len(face_data_list)}/{face_count} faces")

        # Send to backend
        try:
            result = self.sender.send_with_retry(
                faces=face_data_list,
                room_id=self.room_id,
                timestamp=scan_timestamp
            )

            if result is not None:
                # Success
                self.total_faces_sent += len(face_data_list)
                logger.info(
                    f"Successfully sent {len(face_data_list)} faces to backend. "
                    f"Response: {result.get('data', {})}"
                )
            else:
                # Failed after retries - queue for later
                logger.warning("Failed to send faces after retries, queueing for retry...")
                self.queue_manager.enqueue(
                    faces=face_data_list,
                    room_id=self.room_id,
                    timestamp=scan_timestamp,
                    error_msg="Backend unreachable after retries"
                )

        except Exception as e:
            logger.error(f"Error sending faces: {e}")
            # Queue for retry
            self.queue_manager.enqueue(
                faces=face_data_list,
                room_id=self.room_id,
                timestamp=scan_timestamp,
                error_msg=str(e)
            )

        # Update scan count
        self.scan_count += 1

        # Log scan duration
        scan_duration = time.time() - scan_start
        logger.info(f"Scan completed in {scan_duration:.2f}s")

        return True

    def run_continuous(self) -> None:
        """
        Run continuous scanning loop.

        Executes scans at configured interval until stopped.
        When session-aware mode is enabled:
        - Polls for active sessions at SESSION_POLL_INTERVAL when idle
        - Scans at SCAN_INTERVAL when a session is active
        """
        logger.info("Starting continuous scanning loop...")
        logger.info(f"Scan interval: {self.scan_interval}s")
        if self.session_aware:
            logger.info(f"Session-aware mode enabled, poll interval: {self.session_poll_interval}s")

        self.is_running = True

        while self.is_running:
            try:
                # Run single scan (returns False if no active session)
                scan_performed = self.run_single_scan()

                # Log statistics every 10 scans
                if self.scan_count > 0 and self.scan_count % 10 == 0:
                    self._log_statistics()

                # Choose sleep interval based on session state
                if self.is_running:
                    if self.session_aware and not scan_performed:
                        # No active session -- use shorter poll interval
                        sleep_interval = self.session_poll_interval
                        logger.debug(
                            f"No active session, polling again in {sleep_interval}s"
                        )
                    else:
                        # Active session or session-aware disabled -- use scan interval
                        sleep_interval = self.scan_interval
                        logger.debug(f"Waiting {sleep_interval}s until next scan...")

                    time.sleep(sleep_interval)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break

            except Exception as e:
                logger.error(f"Error in scan loop: {e}", exc_info=True)
                # Wait before retrying to avoid tight loop
                time.sleep(5)

        logger.info("Continuous scanning loop stopped")

    def _log_statistics(self) -> None:
        """
        Log device statistics.
        """
        queue_stats = self.queue_manager.get_statistics()

        logger.info("=" * 60)
        logger.info("EDGE DEVICE STATISTICS")
        logger.info(f"Scans completed: {self.scan_count}")
        logger.info(f"Total faces detected: {self.total_faces_detected}")
        logger.info(f"Total faces sent: {self.total_faces_sent}")
        logger.info(f"Queue size: {queue_stats['current_size']}/{queue_stats['max_size']}")
        logger.info(f"Queue utilization: {queue_stats['utilization_pct']:.1f}%")
        logger.info(f"Queue stats: enqueued={queue_stats['total_enqueued']}, "
                   f"dropped={queue_stats['total_dropped']}, "
                   f"succeeded={queue_stats['total_succeeded']}, "
                   f"failed={queue_stats['total_failed']}")
        logger.info("=" * 60)


# Global edge device instance
edge_device: Optional[EdgeDevice] = None


def signal_handler(signum, frame):
    """
    Handle shutdown signals.

    Args:
        signum: Signal number
        frame: Current stack frame
    """
    logger.info(f"Received signal {signum}, initiating shutdown...")

    global edge_device
    if edge_device:
        edge_device.shutdown()

    sys.exit(0)


def main():
    """
    Main entry point.
    """
    global edge_device

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # ASCII banner
    logger.info("=" * 60)
    logger.info("  IAMS Edge Device - Raspberry Pi Face Detection")
    logger.info("  Intelligent Attendance Monitoring System")
    logger.info("=" * 60)

    # Create edge device
    edge_device = EdgeDevice()

    # Initialize
    if not edge_device.initialize():
        logger.error("Failed to initialize edge device")
        sys.exit(1)

    # Run continuous scanning
    try:
        edge_device.run_continuous()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        edge_device.shutdown()


if __name__ == "__main__":
    main()
