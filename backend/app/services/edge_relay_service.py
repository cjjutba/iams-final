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
from app.services.track_fusion_service import TrackFusionService


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
        count = len(room.mobile_clients)
        logger.info(f"EdgeRelay: mobile client registered for room {room_id} (total: {count})")

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

            # Store raw edge detections (unmodified)
            room.last_detections = message
            room.last_update_time = time.monotonic()

            # Build outbound message with identity merged (copy, don't mutate original)
            raw_detections = message.get("detections", [])
            merged_detections = []
            for det in raw_detections:
                out = dict(det)  # shallow copy
                track_id = det.get("track_id")
                if track_id and str(track_id) in room.identity_cache:
                    identity = room.identity_cache[str(track_id)]
                    out["user_id"] = identity.get("user_id")
                    out["name"] = identity.get("name")
                    out["student_id"] = identity.get("student_id")
                    out["similarity"] = identity.get("confidence")
                merged_detections.append(out)

            outbound = dict(message)
            outbound["detections"] = merged_detections

            # Snapshot clients to send outside lock
            clients = list(room.mobile_clients)

        # Send to all mobile clients (outside the lock)
        if not clients:
            return

        dead_clients = []
        for client in clients:
            try:
                if client.client_state == WebSocketState.CONNECTED:
                    await client.send_json(outbound)
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

        # Feed edge detections into track fusion service
        track_fusion_service.update_from_edge(
            room_id,
            message.get("detections", []),
            message.get("frame_width", 640),
            message.get("frame_height", 480),
        )

    # ------------------------------------------------------------------
    # Push identity updates from recognition service
    # ------------------------------------------------------------------

    @staticmethod
    def _bbox_center_distance(bbox_a: dict | list, bbox_b: dict | list) -> float:
        """Compute Euclidean distance between centers of two bboxes.

        Accepts both dict {x,y,width,height} and list [x,y,w,h] formats.
        """
        if isinstance(bbox_a, list):
            ax, ay, aw, ah = bbox_a[0], bbox_a[1], bbox_a[2], bbox_a[3]
        else:
            ax, ay, aw, ah = bbox_a.get("x", 0), bbox_a.get("y", 0), bbox_a.get("width", 0), bbox_a.get("height", 0)

        if isinstance(bbox_b, list):
            bx, by, bw, bh = bbox_b[0], bbox_b[1], bbox_b[2], bbox_b[3]
        else:
            bx, by, bw, bh = bbox_b.get("x", 0), bbox_b.get("y", 0), bbox_b.get("width", 0), bbox_b.get("height", 0)

        cx_a, cy_a = ax + aw / 2, ay + ah / 2
        cx_b, cy_b = bx + bw / 2, by + bh / 2
        return ((cx_a - cx_b) ** 2 + (cy_a - cy_b) ** 2) ** 0.5

    def _match_identity_to_edge_tracks(
        self, room: RoomRelay, mapping: dict
    ) -> str | None:
        """Match a recognition-service identity (with bbox) to the closest edge track_id.

        Uses center-distance between the recognition bbox and the latest edge
        detection bboxes. Returns the closest track_id if within a reasonable
        threshold, or None.
        """
        recog_bbox = mapping.get("bbox")
        if not recog_bbox or room.last_detections is None:
            return None

        edge_dets = room.last_detections.get("detections", [])
        if not edge_dets:
            return None

        # Compute distance threshold based on frame size (~15% of frame diagonal)
        fw = room.last_detections.get("frame_width", 1280)
        fh = room.last_detections.get("frame_height", 720)
        max_distance = 0.15 * ((fw ** 2 + fh ** 2) ** 0.5)

        best_track_id = None
        best_dist = max_distance

        for edet in edge_dets:
            ebbox = edet.get("bbox")
            if ebbox is None:
                continue
            dist = self._bbox_center_distance(recog_bbox, ebbox)
            if dist < best_dist:
                best_dist = dist
                best_track_id = edet.get("track_id")

        return best_track_id

    async def push_identity_update(self, room_id: str, mappings: list[dict]) -> None:
        """
        Update identity cache and forward identity_update message to mobile clients.

        Each mapping: {track_id, user_id, name, student_id, confidence, bbox}

        When track_id is missing (recognition service has no edge track IDs),
        uses bbox-proximity matching against the latest edge detections to find
        the closest track_id.

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

                # If no track_id, try to match by bbox proximity to edge detections
                if not track_id:
                    track_id = self._match_identity_to_edge_tracks(room, m)
                    if track_id:
                        m["track_id"] = track_id

                if track_id:
                    room.identity_cache[str(track_id)] = {
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

            # Feed identity updates into track fusion service
            for mapping in mappings:
                edge_track_id = mapping.get("track_id")
                if edge_track_id is not None:
                    try:
                        edge_tid = int(edge_track_id) if isinstance(edge_track_id, str) else edge_track_id
                        track_fusion_service.update_identity(
                            room_id,
                            edge_track_id=edge_tid,
                            user_id=mapping.get("user_id", ""),
                            name=mapping.get("name", ""),
                            student_id=mapping.get("student_id", ""),
                            similarity=mapping.get("confidence", 0.0),
                        )
                    except (ValueError, TypeError):
                        pass

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


# Module-level singletons
edge_relay_manager = EdgeRelayManager()
track_fusion_service = TrackFusionService()
