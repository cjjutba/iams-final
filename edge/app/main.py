"""RPi Camera Gateway — relays Reolink RTSP to VPS mediamtx.

That's all it does. No ML, no frame sampling, no WebSocket.
"""

import signal
import sys
import time

from app.config import (
    RELAY_MODE,
    ROOM_ID,
    RTSP_MAIN,
    TRANSCODE_BITRATE,
    TRANSCODE_FPS,
    TRANSCODE_MAX_BITRATE,
    TRANSCODE_RESOLUTION,
    VPS_RTSP_URL,
)
from app.stream_relay import StreamRelay


def main():
    target = f"{VPS_RTSP_URL}/{ROOM_ID}"
    relay = StreamRelay(
        RTSP_MAIN,
        target,
        mode=RELAY_MODE,
        resolution=TRANSCODE_RESOLUTION,
        bitrate=TRANSCODE_BITRATE,
        max_bitrate=TRANSCODE_MAX_BITRATE,
        fps=TRANSCODE_FPS,
    )

    def shutdown(signum, frame):
        print(f"Received signal {signum}, stopping...")
        relay.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"Starting RTSP relay ({RELAY_MODE} mode): {RTSP_MAIN} -> {target}")
    relay.start()

    try:
        while True:
            if not relay.is_alive():
                print("Relay died, restarting...")
                relay.start()
            time.sleep(5)
    except KeyboardInterrupt:
        relay.stop()


if __name__ == "__main__":
    main()
