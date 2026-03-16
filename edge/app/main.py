"""
RPi Camera Gateway -- Ultra-lightweight entry point.
1. Start FFmpeg sub-stream relay to VPS mediamtx
2. Sample main stream at 2-3 FPS, send JPEG frames to VPS via WebSocket
3. Handle offline queuing and reconnection
"""
import asyncio
import json
import logging
import time

import websockets

from app.config import EDGE_API_KEY, RECONNECT_MAX_DELAY, ROOM_ID, VPS_WS_URL
from app.frame_sampler import FrameSampler
from app.stream_relay import StreamRelay

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


async def run_gateway():
    """Main gateway loop."""
    relay = StreamRelay()
    sampler = FrameSampler()

    # Start sub-stream relay (FFmpeg background thread)
    relay.start()

    # Start main-stream sampler
    sampler.start()

    reconnect_delay = 1
    ws_url = f"{VPS_WS_URL}/{ROOM_ID}?key={EDGE_API_KEY}"

    while True:
        try:
            logger.info(f"Connecting to VPS: {ws_url}")
            async with websockets.connect(ws_url, ping_interval=10) as ws:
                logger.info("Connected to VPS WebSocket")
                reconnect_delay = 1  # Reset on successful connect

                # Drain offline queue first
                queued = sampler.drain_queue()
                for msg in queued:
                    msg.pop("queued_at", None)
                    await ws.send(json.dumps(msg))
                if queued:
                    logger.info(f"Sent {len(queued)} queued frames")

                # Main sampling loop
                while True:
                    t_start = time.time()

                    # Sample and send frame
                    frame_msg = sampler.sample_frame()
                    if frame_msg:
                        await ws.send(json.dumps(frame_msg))

                    # Periodic heartbeat
                    if int(time.time()) % 10 == 0:
                        try:
                            import psutil
                            cpu = psutil.cpu_percent()
                            ram = psutil.virtual_memory().percent
                        except ImportError:
                            cpu = 0
                            ram = 0
                        heartbeat = {
                            "type": "heartbeat",
                            "room_id": ROOM_ID,
                            "camera_status": "connected",
                            "cpu_percent": cpu,
                            "ram_percent": ram,
                        }
                        await ws.send(json.dumps(heartbeat))

                    # Rate limit
                    elapsed = time.time() - t_start
                    sleep_time = max(0, sampler._frame_interval - elapsed)
                    await asyncio.sleep(sleep_time)

        except (websockets.ConnectionClosed, OSError, ConnectionRefusedError) as e:
            logger.warning(f"VPS connection lost: {e}. Reconnecting in {reconnect_delay}s...")

            # Queue frames while disconnected
            for _ in range(3):
                frame_msg = sampler.sample_frame()
                if frame_msg:
                    sampler.queue_frame(frame_msg)
                await asyncio.sleep(sampler._frame_interval)

            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, RECONNECT_MAX_DELAY)

        except Exception as e:
            logger.error(f"Gateway error: {e}", exc_info=True)
            await asyncio.sleep(5)


def main():
    asyncio.run(run_gateway())


if __name__ == "__main__":
    main()
