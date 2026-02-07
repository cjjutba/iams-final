# Backend Core Specialist - Memory

## Project Stack
- FastAPI 0.128.0, Pydantic 2.12.5, SQLAlchemy 2.0.46, Starlette 0.50.0
- PostgreSQL via Supabase, JWT auth (python-jose), bcrypt 5.0.0
- Python-multipart for file uploads

## Key Patterns & Lessons

### Pydantic v2 Migration Issues
- **UUID -> str coercion**: Pydantic v2 lax mode does NOT auto-coerce `uuid.UUID` to `str`. All response schemas with `id: str` fields backed by SQLAlchemy `UUID(as_uuid=True)` columns need `@field_validator("id", mode="before")` to convert. See [pydantic-uuid-patterns.md](pydantic-uuid-patterns.md).
- **Deprecated methods**: `.from_orm()` -> `.model_validate()`, `.dict()` -> `.model_dump()`. All routers should use v2 methods.
- `from_attributes = True` in Config class enables ORM mode in Pydantic v2.

### Schema Files with UUID Validators
- `backend/app/schemas/user.py` - UserResponse.id
- `backend/app/schemas/schedule.py` - ScheduleResponse (id, faculty_id, room_id), RoomInfo.id
- `backend/app/schemas/attendance.py` - AttendanceRecordResponse (id, student_id, schedule_id), EarlyLeaveResponse.id, AlertResponse (id, attendance_id, student_id, schedule_id)
- `backend/app/schemas/notification.py` - NotificationResponse (id, user_id)

### Repository Method Signatures (Common Pitfalls)
- `ScheduleRepository.get_current_schedule(room_id, day_of_week, current_time)` - requires 3 args, NOT just room_id
- Called from `face.py` Edge API `/process` endpoint using `request.timestamp.weekday()` and `request.timestamp.time()`

### Import Organization
- `import io` should be at module top level in `face.py`, not inside loop bodies
- Face router uses: `io.BytesIO()` for PIL image -> bytes conversion in both `/recognize` and `/process`

### Edge API Contract (face.py /process)
- No auth (trusted network), processes base64 face images from RPi
- Logs presence via PresenceService when schedule is found for room+time
- Response uses `model_dump()` to serialize MatchedUser list into dict

### Response Schema Notes
- `AttendanceRecordResponse.student_name` and `.subject_code` are Optional[str]=None -- NOT populated by model_validate() since they aren't model attributes. They must be populated manually or left as None.
- `FaceStatusResponse` must include `embedding_id: Optional[int] = None` to match the dict returned by `face_service.get_face_status()`

### Attendance Router Route Ordering
- Static paths (`/alerts`, `/export`, `/today`, `/today/{id}`, `/me`, `/me/summary`, `/live/{id}`) MUST come before `/{attendance_id}` to avoid path parameter conflicts.
- `/early-leaves/` and `/alerts` both exist -- `/alerts` is the enriched version with student/schedule info for mobile, `/early-leaves/` is the raw event list.

### Notification System
- Model: `backend/app/models/notification.py` (9th core table: notifications)
- Schema: `backend/app/schemas/notification.py`
- Repository: `backend/app/repositories/notification_repository.py`
- Router: `backend/app/routers/notifications.py`
- Mounted at `/api/v1/notifications` in main.py

### Auth Service Methods
- `forgot_password(email)` - MVP stub, always returns success (prevents email enumeration)
- `update_profile(user_id, update_data)` - Self-service, only allows email/phone updates
- `change_password(user_id, old_password, new_password)` - Full password change with validation

### Export Endpoint
- `GET /attendance/export` supports CSV (StreamingResponse) and JSON formats
- Faculty-only, checks schedule ownership via faculty_id comparison
- Uses `attendance_repo.get_by_schedule_date_range()` added to AttendanceRepository

## Files NOT to Touch
- face.py, websocket.py routers - handled by another agent
- Database/migration files
