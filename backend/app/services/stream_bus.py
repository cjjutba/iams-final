"""
StreamBus — Stub module (pending replacement in Task 3).

This is a temporary stub that keeps the existing PresenceService and
WebSocket broadcaster from crashing on import.  Task 3 will replace the
Redis Streams bus with direct WebSocket broadcasting.
"""

import logging

logger = logging.getLogger(__name__)

# Stream key constants (kept for compatibility until Task 3 removes them)
STREAM_ATTENDANCE = "stream:attendance"
STREAM_ALERTS = "stream:alerts"
STREAM_METRICS = "stream:metrics"


class StreamBus:
    """No-op StreamBus stub — all publishes are silently dropped."""

    def __init__(self):
        self.redis = None

    async def publish_attendance(self, schedule_id: str, payload: dict):
        logger.debug(f"[stream_bus stub] attendance event dropped: {payload.get('event', '?')}")

    async def publish_alert(self, alert: dict):
        logger.debug(f"[stream_bus stub] alert dropped: {alert.get('type', '?')}")

    async def ensure_group(self, stream: str, group: str):
        pass

    async def consume_multiple(self, **kwargs):
        return []

    async def ack(self, stream: str, group: str, msg_id: str):
        pass


_bus: StreamBus | None = None


async def get_stream_bus() -> StreamBus:
    global _bus
    if _bus is None:
        _bus = StreamBus()
    return _bus
