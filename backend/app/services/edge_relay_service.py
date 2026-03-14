"""
Edge Relay Service

Manages real-time relay of face detection bounding boxes from edge devices
(Raspberry Pi) to mobile clients via WebSocket.

Architecture:
    RPi (MediaPipe detections) --WS--> EdgeRelayManager --WS--> Mobile clients
                                            ^
                                            |
                    Recognition Service --> identity_cache (track_id -> user info)

The edge device pushes lightweight bounding-box data at camera frame rate.
The VPS recognition service runs at ~2 FPS and pushes identity mappings
(track_id -> user_id/name) which are merged into the relay stream.
"""

import asyncio
import time
from dataclasses import dataclass, field

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.config import logger


@dataclass
class RoomRelay:
    """Per-room relay state."""

    room_id: str
    edge_ws: WebSocket | None = None
    mobile_clients: set = field(default_factory=set)  # set of WebSocket
    last_detections: dict | None = None
    last_update_time: float = 0.0
    # track_id -> {user_id, name, student_id, confidence}
    identity_cache: dict[str, dict] = field(default_factory=dict)


class EdgeRelayManager:
    """
    Singleton manager for relaying edge device detections to mobile clients.

    Thread-safe via asyncio.Lock. All public methods are async.
    """

    def __init__(self):
        self._rooms: dict[str, RoomRelay] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Edge device registration
    # ------------------------------------------------------------------

    async def register_edge(self, room_id: str, ws: WebSocket) -> None:
        """Register an edge device WebSocket for a room."""
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                room = RoomRelay(room_id=room_id)
                self._rooms[room_id] = room
            room.edge_ws = ws
        logger.info(f"EdgeRelay: edge device registered for room {room_id}")

    async def unregister_edge(self, room_id: str) -> None:
        """Unregister the edge device for a room."""
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is not None:
                room.edge_ws = None
                # Clear stale detection data
                room.last_detections = None
                # Keep identity_cache — it can be reused on reconnect
        logger.info(f"EdgeRelay: edge device unregistered for room {room_id}")

    # ------------------------------------------------------------------
    # Mobile client registration
    # ------------------------------------------------------------------

    async def register_mobile(self, room_id: str, ws: WebSocket) -> None:
        """Register a mobile client WebSocket for a room."""
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                room = RoomRelay(room_id=room_id)
                self._rooms[room_id] = room
            room.mobile_clients.add(ws)
        logger.info(
            f"EdgeRelay: mobile client registered for room {room_id} "
            f"(total: {len(self._rooms.get(room_id, RoomRelay(room_id=room_id)).mobile_clients)})"
        )

    async def unregister_mobile(self, room_id: str, ws: WebSocket) -> None:
        """Unregister a mobile client WebSocket from a room."""
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is not None:
                room.mobile_clients.discard(ws)
                remaining = len(room.mobile_clients)
                # Clean up room if no edge device and no mobile clients
                if room.edge_ws is None and not room.mobile_clients:
                    del self._rooms[room_id]
        logger.debug(f"EdgeRelay: mobile client unregistered for room {room_id}")

    # ------------------------------------------------------------------
    # Relay edge detections to mobile clients
    # ------------------------------------------------------------------

    async def relay_edge_detections(self, room_id: str, message: dict) -> None:
        """
        Relay detection data from edge device to all mobile clients.

        Merges cached identity info into detections before forwarding.
        Sends outside the lock to avoid holding it during I/O.
        Cleans up dead clients automatically.
        """
        # Snapshot state under lock
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return

            # Store latest detections
            room.last_detections = message
            room.last_update_time = time.monotonic()

            # Merge identity cache into detections
            detections = message.get("detections", [])
            for det in detections:
                track_id = det.get("track_id")
                if track_id and track_id in room.identity_cache:
                    identity = room.identity_cache[track_id]
                    det["user_id"] = identity.get("user_id")
                    det["name"] = identity.get("name")
                    det["student_id"] = identity.get("student_id")
                    det["similarity"] = identity.get("confidence")

            # Snapshot clients to send outside lock
            clients = list(room.mobile_clients)

        # Send to all mobile clients (outside the lock)
        if not clients:
            return

        dead_clients = []
        for client in clients:
            try:
                if client.client_state == WebSocketState.CONNECTED:
                    await client.send_json(message)
                else:
                    dead_clients.append(client)
            except Exception:
                dead_clients.append(client)

        # Clean up dead clients
        if dead_clients:
            async with self._lock:
                room = self._rooms.get(room_id)
                if room is not None:
                    for dc in dead_clients:
                        room.mobile_clients.discard(dc)
                    logger.debug(
                        f"EdgeRelay: cleaned up {len(dead_clients)} dead client(s) "
                        f"for room {room_id}"
                    )

    # ------------------------------------------------------------------
    # Push identity updates from recognition service
    # ------------------------------------------------------------------

    async def push_identity_update(self, room_id: str, mappings: list[dict]) -> None:
        """
        Update identity cache and forward identity_update message to mobile clients.

        Each mapping: {track_id, user_id, name, student_id, confidence, bbox}

        Prunes cache to 100 entries (LRU-style: oldest entries removed first).
        """
        if not mappings:
            return

        # Update cache under lock, snapshot clients
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return

            for m in mappings:
                track_id = m.get("track_id")
                if track_id:
                    room.identity_cache[track_id] = {
                        "user_id": m.get("user_id"),
                        "name": m.get("name"),
                        "student_id": m.get("student_id"),
                        "confidence": m.get("confidence"),
                    }

            # Prune to 100 entries (remove oldest)
            if len(room.identity_cache) > 100:
                excess = len(room.identity_cache) - 100
                keys_to_remove = list(room.identity_cache.keys())[:excess]
                for k in keys_to_remove:
                    del room.identity_cache[k]

            clients = list(room.mobile_clients)

        # Build identity_update message
        identity_msg = {
            "type": "identity_update",
            "room_id": room_id,
            "mappings": mappings,
        }

        # Send outside lock
        dead_clients = []
        for client in clients:
            try:
                if client.client_state == WebSocketState.CONNECTED:
                    await client.send_json(identity_msg)
                else:
                    dead_clients.append(client)
            except Exception:
                dead_clients.append(client)

        if dead_clients:
            async with self._lock:
                room = self._rooms.get(room_id)
                if room is not None:
                    for dc in dead_clients:
                        room.mobile_clients.discard(dc)

    # ------------------------------------------------------------------
    # Status / helpers
    # ------------------------------------------------------------------

    async def get_room_status(self, room_id: str) -> dict | None:
        """Get the current relay status for a room."""
        async with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return None
            return {
                "room_id": room_id,
                "edge_connected": room.edge_ws is not None,
                "mobile_clients": len(room.mobile_clients),
                "identity_cache_size": len(room.identity_cache),
                "last_update_time": room.last_update_time,
                "has_detections": room.last_detections is not None,
            }

    def has_edge_device(self, room_id: str) -> bool:
        """
        Synchronous check if an edge device is connected for a room.

        This is safe to call without await because it only reads an attribute
        and Python's GIL makes dict reads atomic.
        """
        room = self._rooms.get(room_id)
        return room is not None and room.edge_ws is not None


# Module-level singleton
edge_relay_manager = EdgeRelayManager()
