"""
Queue Manager for Offline Handling

Implements bounded queue with TTL for handling backend unavailability.

Features:
- Bounded deque with max 500 items
- 5-minute TTL for stale entries
- Automatic retry worker with exponential backoff
- Thread-safe queue operations
- Queue statistics and monitoring
"""

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.config import config, logger
from app.processor import FaceData


@dataclass
class QueueEntry:
    """
    Queue entry with metadata.

    Attributes:
        faces: List of face data
        room_id: Room identifier
        timestamp: Original scan timestamp
        enqueued_at: When this entry was added to queue
        retry_count: Number of retry attempts
        last_error: Last error message (optional)
    """

    faces: list[FaceData]
    room_id: str
    timestamp: datetime
    enqueued_at: float = field(default_factory=time.time)
    retry_count: int = 0
    last_error: str | None = None

    def is_stale(self, ttl_seconds: int) -> bool:
        """
        Check if entry has exceeded TTL.

        Args:
            ttl_seconds: Time-to-live in seconds

        Returns:
            True if entry is stale
        """
        age = time.time() - self.enqueued_at
        return age > ttl_seconds

    def to_dict(self) -> dict:
        """Convert to dictionary for logging"""
        return {
            "room_id": self.room_id,
            "timestamp": self.timestamp.isoformat(),
            "face_count": len(self.faces),
            "enqueued_at": datetime.fromtimestamp(self.enqueued_at).isoformat(),
            "retry_count": self.retry_count,
            "age_seconds": int(time.time() - self.enqueued_at),
        }


class QueueManager:
    """
    Manages offline queue for failed requests.

    Implements bounded queue with TTL and automatic retry worker.
    Thread-safe for concurrent access.
    """

    def __init__(self):
        self.max_size = config.QUEUE_MAX_SIZE
        self.ttl_seconds = config.QUEUE_TTL_SECONDS
        self.retry_interval = config.RETRY_INTERVAL_SECONDS
        self.max_retry_attempts = config.RETRY_MAX_ATTEMPTS

        # Bounded deque for FIFO queue
        self._queue: deque[QueueEntry] = deque(maxlen=self.max_size)

        # Thread safety
        self._lock = threading.Lock()

        # Statistics
        self.total_enqueued = 0
        self.total_dropped = 0
        self.total_retried = 0
        self.total_succeeded = 0
        self.total_failed = 0

    def enqueue(self, faces: list[FaceData], room_id: str, timestamp: datetime, error_msg: str | None = None) -> bool:
        """
        Add entry to queue.

        Args:
            faces: List of face data
            room_id: Room identifier
            timestamp: Original scan timestamp
            error_msg: Error message that caused queuing

        Returns:
            True if enqueued, False if queue is full

        Notes:
            - If queue is full, oldest entry is dropped automatically
            - Thread-safe operation
        """
        with self._lock:
            # Check if queue is full (deque handles this automatically)
            was_full = len(self._queue) >= self.max_size

            # Create queue entry
            entry = QueueEntry(faces=faces, room_id=room_id, timestamp=timestamp, last_error=error_msg)

            # Add to queue (oldest is dropped if full)
            self._queue.append(entry)

            self.total_enqueued += 1

            if was_full:
                self.total_dropped += 1
                logger.warning(
                    f"Queue full ({self.max_size} items), dropped oldest entry. New entry: {entry.to_dict()}"
                )
            else:
                logger.info(f"Enqueued entry: {entry.to_dict()}. Queue size: {len(self._queue)}/{self.max_size}")

            return True

    def dequeue(self) -> QueueEntry | None:
        """
        Remove and return oldest entry from queue.

        Returns:
            Queue entry or None if queue is empty

        Notes:
            - Thread-safe operation
            - Returns None if queue is empty
        """
        with self._lock:
            if not self._queue:
                return None

            entry = self._queue.popleft()
            return entry

    def peek(self) -> QueueEntry | None:
        """
        View oldest entry without removing it.

        Returns:
            Queue entry or None if queue is empty
        """
        with self._lock:
            if not self._queue:
                return None
            return self._queue[0]

    def remove_stale_entries(self) -> int:
        """
        Remove entries that have exceeded TTL.

        Returns:
            Number of stale entries removed

        Notes:
            - Thread-safe operation
            - Logs dropped entries
        """
        with self._lock:
            original_size = len(self._queue)

            # Filter out stale entries
            fresh_entries = deque(
                (entry for entry in self._queue if not entry.is_stale(self.ttl_seconds)), maxlen=self.max_size
            )

            dropped_count = original_size - len(fresh_entries)
            self._queue = fresh_entries

            if dropped_count > 0:
                self.total_dropped += dropped_count
                logger.warning(
                    f"Dropped {dropped_count} stale entries (TTL={self.ttl_seconds}s). "
                    f"Queue size: {len(self._queue)}/{self.max_size}"
                )

            return dropped_count

    def size(self) -> int:
        """
        Get current queue size.

        Returns:
            Number of entries in queue
        """
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        """Check if queue is empty"""
        return self.size() == 0

    def clear(self) -> int:
        """
        Clear all entries from queue.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            size = len(self._queue)
            self._queue.clear()
            logger.info(f"Cleared {size} entries from queue")
            return size

    def get_statistics(self) -> dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Dictionary with queue metrics
        """
        with self._lock:
            return {
                "current_size": len(self._queue),
                "max_size": self.max_size,
                "total_enqueued": self.total_enqueued,
                "total_dropped": self.total_dropped,
                "total_retried": self.total_retried,
                "total_succeeded": self.total_succeeded,
                "total_failed": self.total_failed,
                "utilization_pct": (len(self._queue) / self.max_size * 100) if self.max_size > 0 else 0,
            }

    def get_entries_snapshot(self) -> list[dict[str, Any]]:
        """
        Get snapshot of queue entries for debugging.

        Returns:
            List of entry dictionaries
        """
        with self._lock:
            return [entry.to_dict() for entry in list(self._queue)[:10]]  # First 10 entries


class RetryWorker:
    """
    Background worker for retrying failed requests.

    Runs in separate thread and processes queue entries periodically.
    """

    def __init__(self, queue_manager: QueueManager, sender):
        """
        Initialize retry worker.

        Args:
            queue_manager: Queue manager instance
            sender: Backend sender instance (BackendSender or SyncBackendSender)
        """
        self.queue_manager = queue_manager
        self.sender = sender
        self.is_running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """
        Start retry worker in background thread.
        """
        if self.is_running:
            logger.warning("Retry worker already running")
            return

        self.is_running = True
        self._stop_event.clear()

        self._thread = threading.Thread(target=self._run_worker, daemon=True)
        self._thread.start()

        logger.info("Retry worker started")

    def stop(self) -> None:
        """
        Stop retry worker gracefully.
        """
        if not self.is_running:
            return

        logger.info("Stopping retry worker...")

        self.is_running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=5)

        logger.info("Retry worker stopped")

    def _run_worker(self) -> None:
        """
        Main worker loop (runs in background thread).
        """
        logger.info("Retry worker loop started")

        while self.is_running and not self._stop_event.is_set():
            try:
                # Remove stale entries
                self.queue_manager.remove_stale_entries()

                # Process queue
                if not self.queue_manager.is_empty():
                    self._process_queue()

                # Wait before next iteration
                self._stop_event.wait(timeout=self.queue_manager.retry_interval)

            except Exception as e:
                logger.error(f"Retry worker error: {e}")
                time.sleep(5)  # Avoid tight loop on persistent errors

        logger.info("Retry worker loop exited")

    def _process_queue(self) -> None:
        """
        Process one batch of queue entries.
        """
        queue_size = self.queue_manager.size()
        logger.debug(f"Processing queue ({queue_size} entries)...")

        processed_count = 0
        success_count = 0
        failed_count = 0

        # Process up to 10 entries per batch
        batch_size = min(10, queue_size)

        for _ in range(batch_size):
            entry = self.queue_manager.dequeue()
            if entry is None:
                break

            processed_count += 1

            # Try to send
            try:
                result = self.sender.send_with_retry(
                    faces=entry.faces,
                    room_id=entry.room_id,
                    timestamp=entry.timestamp,
                    max_attempts=self.queue_manager.max_retry_attempts,
                )

                if result is not None:
                    # Success
                    success_count += 1
                    self.queue_manager.total_succeeded += 1
                    self.queue_manager.total_retried += 1

                    logger.info(
                        f"Successfully retried entry: {entry.to_dict()}. Queue size: {self.queue_manager.size()}"
                    )
                else:
                    # Failed after retries
                    failed_count += 1
                    self.queue_manager.total_failed += 1

                    # Re-queue if not exceeded max attempts
                    if entry.retry_count < self.queue_manager.max_retry_attempts:
                        entry.retry_count += 1
                        entry.last_error = "Max retries exceeded"
                        self.queue_manager.enqueue(
                            entry.faces, entry.room_id, entry.timestamp, error_msg=entry.last_error
                        )
                    else:
                        logger.error(f"Permanently failed after {entry.retry_count} attempts: {entry.to_dict()}")

            except Exception as e:
                logger.error(f"Error retrying entry: {e}")
                failed_count += 1

        if processed_count > 0:
            logger.info(
                f"Batch processed: {processed_count} entries "
                f"({success_count} succeeded, {failed_count} failed). "
                f"Queue size: {self.queue_manager.size()}"
            )
