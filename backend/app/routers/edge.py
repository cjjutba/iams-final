"""
Edge Device Router

API endpoints for monitoring edge device (Raspberry Pi) status.
Edge devices are identified by rooms with configured camera_endpoint.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.user import User
from app.services import session_manager
from app.utils.dependencies import get_current_user

router = APIRouter()


@router.get("/status", status_code=status.HTTP_200_OK)
def get_edge_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Get Edge Device Status**

    Returns status of all rooms with configured camera endpoints (edge devices).
    Each room with a camera_endpoint represents a connected Raspberry Pi.

    Shows:
    - Total configured devices
    - Active devices (rooms with active sessions)
    - Per-device details (room name, building, endpoint, session status)
    """
    # Get all rooms with camera endpoints configured
    rooms = (
        db.query(Room)
        .filter(Room.camera_endpoint.isnot(None), Room.camera_endpoint != "")
        .order_by(Room.name)
        .all()
    )

    # Get all schedules to check active sessions per room
    devices = []
    active_count = 0

    for room in rooms:
        # Check if any schedule in this room has an active session
        room_schedules = (
            db.query(Schedule)
            .filter(Schedule.room_id == room.id, Schedule.is_active.is_(True))
            .all()
        )

        has_active_session = False
        active_schedule_id = None
        for sched in room_schedules:
            if session_manager.is_session_active(str(sched.id)):
                has_active_session = True
                active_schedule_id = str(sched.id)
                break

        if has_active_session:
            active_count += 1

        session_info = None
        if active_schedule_id:
            info = session_manager.get_session_info(active_schedule_id)
            if info:
                session_info = {
                    "started_at": info.get("started_at", "").isoformat() if info.get("started_at") else None,
                    "scan_count": info.get("scan_count", 0),
                    "last_scan_at": info.get("last_scan_at", "").isoformat() if info.get("last_scan_at") else None,
                }

        devices.append(
            {
                "id": str(room.id),
                "name": room.name,
                "building": room.building,
                "camera_endpoint": room.camera_endpoint,
                "is_active": room.is_active,
                "status": "scanning" if has_active_session else "idle",
                "session": session_info,
            }
        )

    return {
        "total_devices": len(devices),
        "connected_devices": active_count,
        "idle_devices": len(devices) - active_count,
        "devices": devices,
    }
