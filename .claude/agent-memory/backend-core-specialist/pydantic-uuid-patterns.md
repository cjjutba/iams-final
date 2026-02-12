# Pydantic v2 UUID-to-String Coercion Pattern

## Problem
SQLAlchemy models use `UUID(as_uuid=True)` which returns Python `uuid.UUID` objects.
Pydantic v2 response schemas define these fields as `id: str`.
Pydantic v2's str validator in lax mode does NOT auto-coerce UUID -> str, causing validation errors.

## Solution
Add a `@field_validator` with `mode="before"` to each response schema that has str-typed UUID fields:

```python
from uuid import UUID
from pydantic import BaseModel, field_validator

class MyResponse(BaseModel):
    id: str
    foreign_key_id: str

    @field_validator("id", "foreign_key_id", mode="before")
    @classmethod
    def coerce_uuid_to_str(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True
```

## Affected Schemas in This Project
- `UserResponse` (id)
- `ScheduleResponse` (id, faculty_id, room_id)
- `RoomInfo` (id)
- `AttendanceRecordResponse` (id, student_id, schedule_id)
- `EarlyLeaveResponse` (id)

## Alternative Approach (not used)
Could use `Annotated[str, BeforeValidator(lambda v: str(v) if isinstance(v, UUID) else v)]`
as a reusable type alias. Consider if more schemas need this pattern.
