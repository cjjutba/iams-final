"""
Rooms Router

API endpoints for room management and lookup.
Includes CRUD operations (admin only) and edge device room lookup.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.room import Room
from app.models.user import User
from app.schemas.room import RoomCreate, RoomUpdate
from app.utils.dependencies import get_current_admin, get_current_user

router = APIRouter()


@router.get("/lookup", status_code=status.HTTP_200_OK)
def lookup_room(
    name: str = Query(..., description="Room name to look up (e.g., 'Room 103')"),
    db: Session = Depends(get_db),
):
    """
    Look up a room by name and return its UUID.

    Used by edge devices to resolve ROOM_NAME -> ROOM_ID at startup.
    No authentication required (edge devices don't have user tokens).
    """
    room = db.query(Room).filter(Room.name == name, Room.is_active.is_(True)).first()

    if not room:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"No active room found with name '{name}'"},
        )

    return {
        "id": str(room.id),
        "name": room.name,
        "building": room.building,
        "capacity": room.capacity,
    }


@router.get("/", status_code=status.HTTP_200_OK)
def list_rooms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **List All Rooms**

    Get all rooms in the system.

    Requires authentication.
    """
    rooms = db.query(Room).all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "building": r.building,
            "capacity": r.capacity,
            "camera_endpoint": r.camera_endpoint,
            "is_active": r.is_active,
        }
        for r in rooms
    ]


@router.get("/{room_id}", status_code=status.HTTP_200_OK)
def get_room(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Get Room by ID**

    Retrieve room details by UUID.

    Requires authentication.
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return {
        "id": str(room.id),
        "name": room.name,
        "building": room.building,
        "capacity": room.capacity,
        "camera_endpoint": room.camera_endpoint,
        "is_active": room.is_active,
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_room(
    data: RoomCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    **Create Room** (Admin Only)

    Create a new room in the system.

    Requires admin authentication.
    """
    room = Room(
        name=data.name,
        building=data.building,
        capacity=data.capacity,
        camera_endpoint=data.camera_endpoint,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return {
        "id": str(room.id),
        "name": room.name,
        "building": room.building,
        "capacity": room.capacity,
        "camera_endpoint": room.camera_endpoint,
        "is_active": room.is_active,
    }


@router.patch("/{room_id}", status_code=status.HTTP_200_OK)
def update_room(
    room_id: str,
    data: RoomUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    **Update Room** (Admin Only)

    Update room details. Only provided fields will be updated.

    Requires admin authentication.
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(room, key, value)

    db.commit()
    db.refresh(room)
    return {
        "id": str(room.id),
        "name": room.name,
        "building": room.building,
        "capacity": room.capacity,
        "camera_endpoint": room.camera_endpoint,
        "is_active": room.is_active,
    }


@router.delete("/{room_id}", status_code=status.HTTP_200_OK)
def delete_room(
    room_id: str,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    **Delete Room** (Admin Only)

    Permanently delete a room from the system.

    Requires admin authentication.
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    db.delete(room)
    db.commit()
    return {"success": True, "message": "Room deleted"}
