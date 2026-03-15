"""
Edge WebSocket Client — Real-time bbox push to VPS

Maintains a persistent WebSocket connection to the VPS backend,
sending face detection bounding boxes in real-time so the mobile
app can overlay them on the live camera feed.

Key design decisions:
- Runs in a daemon background thread (non-blocking to detection loop)
- Uses a bounded queue (maxsize=30) to decouple detection from sending
- Drops oldest messages when queue is full (freshness > completeness)
- Auto-reconnects with exponential backoff (1s → 30s max)
- Uses websocket-client (synchronous) for simpler thread control
"""

import json
import logging
import queue
import threading
from datetime import datetime, timezone

import websocket

from app.config import Config

logger = logging.getLogger("edge.websocket")


class EdgeWebSocketClient:
    """WebSocket client that pushes face detection bboxes to the VPS."""

    def __init__(self) -> None:
        self._ws: websocket.WebSocket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._queue: queue.Queue = queue.Queue(maxsize=30)
        self._room_id: str | None = None
        self._connected = False
        self._lock = threading.Lock()
        self._stats = {
            "messages_sent": 0,
            "messages_dropped": 0,
            "reconnects": 0,
        }

    @property
    def is_connected(self) -> bool:
        """True if the WebSocket connection is currently open."""
        with self._lock:
            return self._connected

    def start(self, room_id: str) -> bool:
        """
        Start the WebSocket client in a background thread.

        Args:
            room_id: Room identifier appended as query parameter.

        Returns:
            True if the client was started, False if disabled or already running.
        """
        if not Config.EDGE_WS_ENABLED:
            logger.debug("Edge WebSocket is disabled")
            return False

        if self._thread and self._thread.is_alive():
            logger.warning("Edge WebSocket is already running")
            return False

        self._room_id = room_id
        self._stop_event.clear()

        # Clear any stale messages from a previous session
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        self._thread = threading.Thread(
            target=self._run_loop,
            name="edge-websocket",
            daemon=True,
        )
        self._thread.start()

        logger.info("Edge WebSocket client started for room %s", room_id)
        return True

    def stop(self) -> None:
        """Stop the WebSocket client and close the connection."""
        self._stop_event.set()

        # Close the socket to unblock any recv/send
        self._close_ws()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

        self._thread = None
        self._room_id = None
        logger.info("Edge WebSocket client stopped")

    def send_detections(
        self,
        detections: list[dict],
        frame_width: int,
        frame_height: int,
    ) -> None:
        """
        Enqueue a detections message for sending over WebSocket.

        Non-blocking. If the queue is full, the oldest message is dropped
        to make room (freshness matters more than completeness).

        Args:
            detections: List of detection dicts, each with keys:
                        bbox (list[int]), confidence (float), track_id (str).
            frame_width: Width of the source frame in pixels.
            frame_height: Height of the source frame in pixels.
        """
        if not self.is_connected:
            return

        message = {
            "type": "edge_detections",
            "room_id": self._room_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frame_width": frame_width,
            "frame_height": frame_height,
            "detections": detections,
        }

        try:
            self._queue.put_nowait(message)
        except queue.Full:
            # Drop the oldest message and enqueue the new one
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(message)
            except queue.Full:
                pass
            self._stats["messages_dropped"] += 1

    def send_tracked_detections(
        self,
        tracked_objects: list,
        frame_width: int,
        frame_height: int,
        frame_seq: int,
    ) -> None:
        """Send tracked detections with centroid and velocity data."""
        if not self.is_connected:
            return

        detections = []
        for t in tracked_objects:
            detections.append({
                "track_id": t.track_id,
                "bbox": t.bbox,
                "confidence": t.confidence,
                "centroid": list(t.centroid),
                "velocity": list(t.velocity),
            })

        message = {
            "type": "edge_detections",
            "room_id": self._room_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frame_seq": frame_seq,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "detections": detections,
        }

        try:
            self._queue.put_nowait(message)
        except Exception:
            pass

    def get_status(self) -> dict:
        """Return current status and stats for diagnostics."""
        return {
            "connected": self.is_connected,
            "room_id": self._room_id,
            "queue_size": self._queue.qsize(),
            "messages_sent": self._stats["messages_sent"],
            "messages_dropped": self._stats["messages_dropped"],
            "reconnects": self._stats["reconnects"],
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """
        Background thread: connect, send messages, reconnect on failure.

        Uses exponential backoff for reconnection: starts at 1s, doubles
        each time, caps at 30s. Resets to 1s after a successful connection.
        """
        backoff = 1.0
        max_backoff = 30.0

        while not self._stop_event.is_set():
            try:
                self._connect()
                backoff = 1.0  # Reset after successful connection
                self._send_loop()
            except Exception as e:
                logger.warning("Edge WebSocket error: %s", e)

            self._close_ws()

            if not self._stop_event.is_set():
                self._stats["reconnects"] += 1
                logger.info(
                    "Edge WebSocket: reconnecting in %.1fs...", backoff
                )
                self._stop_event.wait(backoff)
                backoff = min(backoff * 2, max_backoff)

    def _connect(self) -> None:
        """Establish WebSocket connection to the VPS."""
        url = Config.get_edge_ws_url()
        ws_url = f"{url}?room_id={self._room_id}"

        logger.info("Edge WebSocket: connecting to %s", ws_url)

        ws = websocket.WebSocket()
        ws.settimeout(30)  # 30s timeout — long enough for idle periods
        ws.connect(ws_url)

        with self._lock:
            self._ws = ws
            self._connected = True

        logger.info("Edge WebSocket: connected")

    def _send_loop(self) -> None:
        """
        Drain the queue and send messages over the WebSocket.

        Sends application-level JSON pings every 10s when idle.
        Also drains incoming pong/response frames to prevent buffer
        accumulation from causing connection issues.
        """
        import select
        import time as _time

        last_send = _time.monotonic()
        ping_interval = 10.0  # seconds between keepalive pings

        while not self._stop_event.is_set():
            try:
                message = self._queue.get(timeout=0.5)
                self._ws.send(json.dumps(message))
                self._stats["messages_sent"] += 1
                last_send = _time.monotonic()
            except queue.Empty:
                pass  # No messages to send — handled below
            except websocket.WebSocketConnectionClosedException:
                logger.warning("Edge WebSocket: connection closed (send)")
                return
            except OSError as e:
                logger.warning("Edge WebSocket: socket error: %s", e)
                return

            # Drain any incoming frames (pong responses) to prevent
            # receive buffer from accumulating and killing the connection.
            try:
                sock = self._ws.sock
                if sock is not None:
                    while True:
                        readable, _, _ = select.select([sock], [], [], 0)
                        if not readable:
                            break
                        # Read and discard the frame
                        self._ws.recv()
            except websocket.WebSocketConnectionClosedException:
                logger.warning("Edge WebSocket: connection closed (drain)")
                return
            except (OSError, websocket.WebSocketException):
                pass  # Non-fatal — continue

            # Send keepalive ping if idle long enough
            now = _time.monotonic()
            if now - last_send >= ping_interval:
                try:
                    self._ws.send(json.dumps({"type": "ping"}))
                    last_send = now
                except (
                    websocket.WebSocketConnectionClosedException,
                    OSError,
                ):
                    logger.warning("Edge WebSocket: connection lost (ping)")
                    return

    def _close_ws(self) -> None:
        """Close the WebSocket connection if open."""
        with self._lock:
            ws = self._ws
            self._ws = None
            self._connected = False

        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass


# Module-level singleton
edge_ws_client = EdgeWebSocketClient()
