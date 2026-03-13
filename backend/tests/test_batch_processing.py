"""Test the batch processing pipeline.

Unit tests for BatchProcessor that mock Redis to verify enqueue behaviour,
threshold triggering, and start/stop lifecycle without requiring a live
Redis instance.
"""

import asyncio
import json

import pytest
from unittest.mock import patch, AsyncMock

from app.services.batch_processor import BatchProcessor
from app.config import settings


class TestBatchProcessor:
    """Tests for the BatchProcessor class."""

    @pytest.mark.asyncio
    async def test_enqueue_face_pushes_to_redis(self):
        """Faces enqueued go to the correct Redis queue key."""
        mock_redis = AsyncMock()
        mock_redis.rpush = AsyncMock()
        mock_redis.llen = AsyncMock(return_value=1)

        with patch("app.services.batch_processor.get_redis", return_value=mock_redis):
            bp = BatchProcessor()
            face_data = {"image": "base64data", "bbox": [0, 0, 100, 100]}
            await bp.enqueue_face("room_a", face_data)

            # rpush should be called once with the correct queue key
            mock_redis.rpush.assert_called_once()
            call_args = mock_redis.rpush.call_args
            queue_key = call_args[0][0]
            payload = call_args[0][1]

            expected_key = f"{settings.REDIS_BATCH_QUEUE_PREFIX}:room_a"
            assert queue_key == expected_key

            # Verify the payload is JSON-encoded face data
            decoded = json.loads(payload)
            assert decoded["image"] == "base64data"
            assert decoded["bbox"] == [0, 0, 100, 100]

    @pytest.mark.asyncio
    async def test_enqueue_checks_queue_length(self):
        """enqueue_face calls llen on the correct queue key."""
        mock_redis = AsyncMock()
        mock_redis.rpush = AsyncMock()
        mock_redis.llen = AsyncMock(return_value=1)

        with patch("app.services.batch_processor.get_redis", return_value=mock_redis):
            bp = BatchProcessor()
            await bp.enqueue_face("room_b", {"image": "data"})

            expected_key = f"{settings.REDIS_BATCH_QUEUE_PREFIX}:room_b"
            mock_redis.llen.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_enqueue_threshold_triggers_event(self):
        """When queue reaches threshold, _threshold_event is set."""
        mock_redis = AsyncMock()
        mock_redis.rpush = AsyncMock()
        mock_redis.llen = AsyncMock(return_value=settings.REDIS_BATCH_THRESHOLD)

        with patch("app.services.batch_processor.get_redis", return_value=mock_redis):
            bp = BatchProcessor()
            await bp.enqueue_face("room_a", {"image": "data"})
            assert bp._threshold_event.is_set()

    @pytest.mark.asyncio
    async def test_enqueue_above_threshold_triggers_event(self):
        """Above threshold also triggers the event."""
        mock_redis = AsyncMock()
        mock_redis.rpush = AsyncMock()
        mock_redis.llen = AsyncMock(return_value=settings.REDIS_BATCH_THRESHOLD + 5)

        with patch("app.services.batch_processor.get_redis", return_value=mock_redis):
            bp = BatchProcessor()
            await bp.enqueue_face("room_a", {"image": "data"})
            assert bp._threshold_event.is_set()

    @pytest.mark.asyncio
    async def test_enqueue_below_threshold_no_trigger(self):
        """Below threshold, event is not set."""
        mock_redis = AsyncMock()
        mock_redis.rpush = AsyncMock()
        mock_redis.llen = AsyncMock(return_value=3)

        with patch("app.services.batch_processor.get_redis", return_value=mock_redis):
            bp = BatchProcessor()
            await bp.enqueue_face("room_a", {"image": "data"})
            assert not bp._threshold_event.is_set()

    @pytest.mark.asyncio
    async def test_start_creates_background_task(self):
        """BatchProcessor.start() creates a running asyncio task."""
        mock_redis = AsyncMock()
        # Lock not acquired so the loop just sleeps
        mock_redis.set = AsyncMock(return_value=False)

        with patch("app.services.batch_processor.get_redis", return_value=mock_redis):
            bp = BatchProcessor()
            await bp.start()
            assert bp._task is not None
            assert not bp._task.done()

            # Clean up
            await bp.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        """BatchProcessor.stop() cancels the background task."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=False)

        with patch("app.services.batch_processor.get_redis", return_value=mock_redis):
            bp = BatchProcessor()
            await bp.start()
            assert bp._task is not None

            await bp.stop()
            assert bp._task is None

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        """Calling start() twice does not create a second task."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=False)

        with patch("app.services.batch_processor.get_redis", return_value=mock_redis):
            bp = BatchProcessor()
            await bp.start()
            first_task = bp._task

            await bp.start()  # Should be a no-op
            assert bp._task is first_task

            await bp.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self):
        """Calling stop() when not started is a safe no-op."""
        bp = BatchProcessor()
        await bp.stop()  # Should not raise
        assert bp._task is None

    @pytest.mark.asyncio
    async def test_enqueue_multiple_rooms(self):
        """Faces for different rooms go to different queue keys."""
        mock_redis = AsyncMock()
        mock_redis.rpush = AsyncMock()
        mock_redis.llen = AsyncMock(return_value=1)

        with patch("app.services.batch_processor.get_redis", return_value=mock_redis):
            bp = BatchProcessor()
            await bp.enqueue_face("room_a", {"image": "a"})
            await bp.enqueue_face("room_b", {"image": "b"})

            assert mock_redis.rpush.call_count == 2

            keys_used = [call[0][0] for call in mock_redis.rpush.call_args_list]
            assert f"{settings.REDIS_BATCH_QUEUE_PREFIX}:room_a" in keys_used
            assert f"{settings.REDIS_BATCH_QUEUE_PREFIX}:room_b" in keys_used

    @pytest.mark.asyncio
    async def test_initial_state(self):
        """BatchProcessor initialises with correct default state."""
        bp = BatchProcessor()
        assert bp._task is None
        assert not bp._stop_event.is_set()
        assert not bp._threshold_event.is_set()
