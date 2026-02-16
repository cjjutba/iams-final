"""
Camera Configuration

Maps room IDs to RTSP camera URLs for live streaming.
Supports per-room camera_endpoint from the database and a fallback default URL.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings, logger
from app.models.room import Room


def get_camera_url(room_id: str, db: Session) -> Optional[str]:
    """
    Get the RTSP camera URL for a given room.

    Resolution order:
    1. Room.camera_endpoint from the database (if set)
    2. settings.DEFAULT_RTSP_URL (global fallback)
    3. None (no camera configured)

    Args:
        room_id: UUID of the room
        db: SQLAlchemy database session

    Returns:
        RTSP URL string, or None if no camera is configured for this room
    """
    import uuid as uuid_mod

    # Convert string to UUID for SQLite/PostgreSQL compatibility
    if isinstance(room_id, str):
        room_id_val = uuid_mod.UUID(room_id)
    else:
        room_id_val = room_id

    room = db.query(Room).filter(Room.id == room_id_val).first()

    if room and room.camera_endpoint and room.camera_endpoint.startswith("rtsp://"):
        logger.debug(f"Using room-specific camera URL for room {room.name}: {room.camera_endpoint}")
        return room.camera_endpoint

    if settings.DEFAULT_RTSP_URL:
        logger.debug(f"Using default RTSP URL for room {room_id}")
        return settings.DEFAULT_RTSP_URL

    logger.warning(f"No camera URL configured for room {room_id}")
    return None
