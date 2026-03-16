"""
Redis Streams event bus for inter-service communication.
Enterprise pattern: event-driven pipeline with consumer groups.
"""
import json
import logging
import time
from typing import Any

import redis.asyncio as redis

from app.redis_client import get_redis

logger = logging.getLogger(__name__)

# Stream names
STREAM_FRAMES = "stream:frames:{room_id}"
STREAM_DETECTIONS = "stream:detections:{room_id}"
STREAM_RECOGNITION_REQ = "stream:recognition_req"
STREAM_RECOGNITIONS = "stream:recognitions"
STREAM_ATTENDANCE = "stream:attendance:{schedule_id}"
STREAM_ALERTS = "stream:alerts"
STREAM_METRICS = "stream:metrics"


class StreamBus:
    """Redis Streams wrapper for publishing and consuming events."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    # ── Publishing ──────────────────────────────────────────────

    async def publish(
        self, stream: str, data: dict[str, Any], maxlen: int = 100
    ) -> str:
        """Publish a message to a Redis Stream. Returns message ID."""
        # Redis Streams require all values to be strings or bytes
        payload = {"data": json.dumps(data), "ts": str(time.time())}
        msg_id = await self.redis.xadd(stream, payload, maxlen=maxlen)
        return msg_id

    async def publish_frame(self, room_id: str, frame_data: dict) -> str:
        stream = STREAM_FRAMES.format(room_id=room_id)
        return await self.publish(stream, frame_data, maxlen=10)

    async def publish_detections(self, room_id: str, detections: dict) -> str:
        stream = STREAM_DETECTIONS.format(room_id=room_id)
        return await self.publish(stream, detections, maxlen=30)

    async def publish_recognition_request(self, request: dict) -> str:
        return await self.publish(STREAM_RECOGNITION_REQ, request, maxlen=100)

    async def publish_recognition_result(self, result: dict) -> str:
        return await self.publish(STREAM_RECOGNITIONS, result, maxlen=100)

    async def publish_attendance(self, schedule_id: str, update: dict) -> str:
        stream = STREAM_ATTENDANCE.format(schedule_id=schedule_id)
        return await self.publish(stream, update, maxlen=1000)

    async def publish_alert(self, alert: dict) -> str:
        return await self.publish(STREAM_ALERTS, alert, maxlen=500)

    async def publish_metrics(self, metrics: dict) -> str:
        return await self.publish(STREAM_METRICS, metrics, maxlen=100)

    # ── Consuming ───────────────────────────────────────────────

    async def ensure_group(self, stream: str, group: str):
        """Create consumer group if it doesn't exist."""
        try:
            await self.redis.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 1,
        block: int = 5000,
    ) -> list[tuple[str, dict]]:
        """Read messages from a consumer group. Returns [(msg_id, data)]."""
        results = await self.redis.xreadgroup(
            group, consumer, {stream: ">"}, count=count, block=block
        )
        messages = []
        for _stream_name, entries in results:
            for msg_id, fields in entries:
                data_str = fields.get(b"data") or fields.get("data")
                if data_str:
                    if isinstance(data_str, bytes):
                        data_str = data_str.decode()
                    messages.append((msg_id, json.loads(data_str)))
        return messages

    async def ack(self, stream: str, group: str, msg_id: str):
        """Acknowledge a processed message."""
        await self.redis.xack(stream, group, msg_id)

    async def consume_multiple(
        self,
        streams: dict[str, str],
        group: str,
        consumer: str,
        count: int = 1,
        block: int = 5000,
    ) -> list[tuple[str, str, dict]]:
        """Read from multiple streams. Returns [(stream, msg_id, data)]."""
        results = await self.redis.xreadgroup(
            group, consumer, streams, count=count, block=block
        )
        messages = []
        for stream_name, entries in results:
            if isinstance(stream_name, bytes):
                stream_name = stream_name.decode()
            for msg_id, fields in entries:
                data_str = fields.get(b"data") or fields.get("data")
                if data_str:
                    if isinstance(data_str, bytes):
                        data_str = data_str.decode()
                    messages.append((stream_name, msg_id, json.loads(data_str)))
        return messages


# ── Singleton ─────────────────────────────────────────────────

_bus: StreamBus | None = None


async def get_stream_bus() -> StreamBus:
    global _bus
    if _bus is None:
        r = await get_redis()
        _bus = StreamBus(r)
    return _bus
