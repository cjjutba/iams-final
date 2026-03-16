"""
Room Model

Represents classrooms/rooms where attendance is monitored.
"""

import uuid

from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Room(Base):
    """
    Room/Classroom model

    Represents physical classrooms with camera monitoring.

    Attributes:
        id: UUID primary key
        name: Room name/number (e.g., "Room 101")
        building: Building name
        capacity: Room capacity
        camera_endpoint: IP/URL of camera endpoint (optional)
        is_active: Whether the room is active
    """

    __tablename__ = "rooms"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Room details
    name = Column(String(100), nullable=False)
    building = Column(String(100), nullable=False)
    capacity = Column(Integer, nullable=True)
    camera_endpoint = Column(String(255), nullable=True)
    stream_key = Column(String(100), nullable=True)  # mediamtx path / Redis stream key (e.g. "eb-226")

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    # schedules = relationship("Schedule", back_populates="room")

    def __repr__(self):
        return f"<Room(id={self.id}, name={self.name}, building={self.building})>"
