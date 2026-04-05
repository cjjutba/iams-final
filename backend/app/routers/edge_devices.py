"""
Edge Devices Router

Admin-only endpoints for monitoring edge device (camera/room) status.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.user import User
from app.utils.dependencies import get_current_admin

router = APIRouter()


def _get_active_schedule(room: Room, db: Session):
    """Check if there's a currently active schedule in this room."""
    now = datetime.now()
    current_day = now.weekday()  # 0=Monday
    current_time = now.time()

    return (
        db.query(Schedule)
        .filter(
            Schedule.room_id == room.id,
            Schedule.day_of_week == current_day,
            Schedule.start_time <= current_time,
            Schedule.end_time >= current_time,
            Schedule.is_active.is_(True),
        )
        .first()
    )


def _serialize_device(room: Room, db: Session):
    """Serialize a room as an edge device with scanning status."""
    active_schedule = _get_active_schedule(room, db)
    is_scanning = active_schedule is not None

    # Count total schedules for this room
    schedule_count = db.query(Schedule).filter(Schedule.room_id == room.id, Schedule.is_active.is_(True)).count()

    session_data = None
    if active_schedule:
        session_data = {
            "schedule_id": str(active_schedule.id),
            "subject": f"{active_schedule.subject_code} - {active_schedule.subject_name}",
            "started_at": datetime.combine(datetime.today(), active_schedule.start_time).isoformat(),
            "ends_at": datetime.combine(datetime.today(), active_schedule.end_time).isoformat(),
        }

    return {
        "id": str(room.id),
        "name": room.name,
        "building": room.building,
        "camera_endpoint": room.camera_endpoint,
        "stream_key": room.stream_key,
        "is_active": room.is_active,
        "capacity": room.capacity,
        "status": "scanning" if is_scanning else "idle",
        "schedule_count": schedule_count,
        "session": session_data,
    }


@router.get("/status", status_code=status.HTTP_200_OK)
def get_edge_status(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Returns all rooms with camera endpoints configured as edge devices,
    including real-time scanning status based on active schedules.
    """
    rooms = db.query(Room).filter(Room.camera_endpoint.isnot(None), Room.camera_endpoint != "").all()

    devices = [_serialize_device(room, db) for room in rooms]
    scanning_count = sum(1 for d in devices if d["status"] == "scanning")

    return {
        "total_devices": len(devices),
        "scanning_devices": scanning_count,
        "idle_devices": len(devices) - scanning_count,
        "devices": devices,
    }


@router.get("/{device_id}", status_code=status.HTTP_200_OK)
def get_edge_device(
    device_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get detailed info for a single edge device (room with camera).
    Includes assigned schedules.
    """
    room = db.query(Room).filter(Room.id == device_id, Room.camera_endpoint.isnot(None)).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Edge device not found",
        )

    device = _serialize_device(room, db)

    # Add full schedule list
    schedules = (
        db.query(Schedule)
        .filter(Schedule.room_id == room.id, Schedule.is_active.is_(True))
        .order_by(Schedule.day_of_week, Schedule.start_time)
        .all()
    )

    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    device["schedules"] = [
        {
            "id": str(s.id),
            "subject_code": s.subject_code,
            "subject_name": s.subject_name,
            "day_of_week": s.day_of_week,
            "day_name": DAY_NAMES[s.day_of_week] if s.day_of_week < len(DAY_NAMES) else "Unknown",
            "start_time": s.start_time.strftime("%H:%M") if s.start_time else None,
            "end_time": s.end_time.strftime("%H:%M") if s.end_time else None,
            "faculty_id": str(s.faculty_id),
        }
        for s in schedules
    ]

    return device
