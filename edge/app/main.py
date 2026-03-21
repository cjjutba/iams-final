"""RPi Camera Gateway — relays Reolink RTSP to VPS mediamtx.

That's all it does. No ML, no frame sampling, no WebSocket.
"""
import signal
import sys
import time

from app.config import ROOM_ID, RTSP_MAIN, VPS_RTSP_URL
from app.stream_relay import StreamRelay


def main():
    target = f"{VPS_RTSP_URL}/{ROOM_ID}/raw"
    relay = StreamRelay(RTSP_MAIN, target)

    def shutdown(signum, frame):
        print(f"Received signal {signum}, stopping...")
        relay.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"Starting RTSP relay: {RTSP_MAIN} -> {target}")
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
