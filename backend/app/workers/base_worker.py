"""
Base class for Redis Streams workers.
Handles consumer group setup, graceful shutdown, and health metrics.
"""
import asyncio
import json
import logging
import signal
import time
from abc import ABC, abstractmethod

from app.config import settings
from app.redis_client import get_redis
from app.services.stream_bus import StreamBus, get_stream_bus

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """Base class for all stream-consuming workers."""

    def __init__(self, name: str, group: str, consumer_id: str = "worker-1"):
        self.name = name
        self.group = group
        self.consumer_id = consumer_id
        self.running = False
        self.bus: StreamBus | None = None
        self.frames_processed = 0
        self.errors = 0
        self.start_time = time.time()
        self._last_metrics_time = time.time()

    async def setup(self):
        """Initialize connections and models. Override for custom setup."""
        self.bus = await get_stream_bus()
        logger.info(f"[{self.name}] Worker initialized")

    @abstractmethod
    async def get_streams(self) -> dict[str, str]:
        """Return {stream_name: ">"} dict of streams to consume."""
        ...

    @abstractmethod
    async def process_message(self, stream: str, msg_id: str, data: dict):
        """Process a single message from a stream."""
        ...

    async def run(self):
        """Main worker loop."""
        self.running = True
        await self.setup()

        # Create consumer groups for all streams
        streams = await self.get_streams()
        for stream_name in streams:
            await self.bus.ensure_group(stream_name, self.group)

        logger.info(f"[{self.name}] Listening on streams: {list(streams.keys())}")

        while self.running:
            try:
                messages = await self.bus.consume_multiple(
                    streams={s: ">" for s in streams},
                    group=self.group,
                    consumer=self.consumer_id,
                    count=5,
                    block=1000,
                )

                for stream, msg_id, data in messages:
                    try:
                        await self.process_message(stream, msg_id, data)
                        await self.bus.ack(stream, self.group, msg_id)
                        self.frames_processed += 1
                    except Exception as e:
                        self.errors += 1
                        logger.error(
                            f"[{self.name}] Error processing {msg_id}: {e}",
                            exc_info=True,
                        )

                # Publish metrics every 10 seconds
                now = time.time()
                if now - self._last_metrics_time >= 10:
                    await self._publish_metrics()
                    self._last_metrics_time = now

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.name}] Stream read error: {e}", exc_info=True)
                await asyncio.sleep(1)

        logger.info(f"[{self.name}] Worker stopped")

    async def _publish_metrics(self):
        if self.bus:
            await self.bus.publish_metrics(
                {
                    "worker": self.name,
                    "frames_processed": self.frames_processed,
                    "errors": self.errors,
                    "uptime_seconds": int(time.time() - self.start_time),
                }
            )

    def stop(self):
        self.running = False


def run_worker(worker: BaseWorker):
    """Entry point for running a worker as a standalone process."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown(sig, frame):
        logger.info(f"[{worker.name}] Received {sig}, shutting down...")
        worker.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        loop.run_until_complete(worker.run())
    finally:
        loop.close()
