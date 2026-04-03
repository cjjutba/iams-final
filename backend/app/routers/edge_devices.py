"""
Edge Devices Router

Admin-only endpoint for monitoring edge device (camera/room) status.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.room import Room
from app.models.user import User
from app.utils.dependencies import get_current_admin

router = APIRouter()


@router.get("/status", status_code=status.HTTP_200_OK)
def get_edge_status(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Returns a list of rooms that have camera endpoints configured,
    along with their stream keys and online status.
    """
    rooms = (
        db.query(Room)
        .filter(Room.camera_endpoint.isnot(None), Room.camera_endpoint != "")
        .all()
    )

    results = []
    for room in rooms:
        results.append({
            "room_id": str(room.id),
            "room_name": f"{room.name} ({room.building})",
            "camera_endpoint": room.camera_endpoint,
            "stream_key": room.stream_key,
            "is_active": room.is_active,
        })

    return {"success": True, "data": results}
