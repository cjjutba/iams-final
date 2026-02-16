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
- Static paths (`/alerts`, `/export`, `/today`, `/today/{id}`, `/me`, `/me/summary`, `/my-attendance`, `/schedule/{id}`, `/schedule/{id}/summary`, `/live/{id}`, `/manual-entry`) MUST come before `/{attendance_id}` to avoid path parameter conflicts.
- `/early-leaves/` and `/alerts` both exist -- `/alerts` is the enriched version with student/schedule info for mobile, `/early-leaves/` is the raw event list.
- `/me` and `/my-attendance` are aliases for student attendance history (for backward compatibility)
- Manual entry endpoint is `/manual-entry` (NOT `/manual`)

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

### Repository Pattern
- All repositories should include `model = ModelClass` class attribute for test access
- Example: `AttendanceRepository.model = AttendanceRecord` allows tests to query directly
- This enables test code like: `db_session.query(repo.model).filter(...).all()`

### AttendanceStatus Enum
- Values: PRESENT, LATE, ABSENT, EARLY_LEAVE, EXCUSED (5 statuses)
- Defined in `backend/app/models/attendance_record.py`
- Used in both model and schemas for validation
- Faculty can manually set EXCUSED status via `/manual-entry` endpoint

### Test Fixtures - Timing Considerations
- `test_schedule` fixture uses current time as `start_time` to ensure tests run within grace period
- Grace period is 15 minutes (settings.GRACE_PERIOD_MINUTES)
- Attendance logic: if check-in <= start_time + 15min → PRESENT, else → LATE
- Tests that mock time (e.g., late detection) use `patch('app.services.presence_service.datetime')`

### Live Stream System
- **Service**: `backend/app/services/live_stream_service.py` - manages RTSP captures + frame processing
- **Camera config**: `backend/app/services/camera_config.py` - room_id -> RTSP URL resolution
- **Router**: `backend/app/routers/live_stream.py` - WebSocket at `/api/v1/stream/{schedule_id}`
- **Settings**: `STREAM_FPS=3`, `STREAM_QUALITY=65`, `STREAM_WIDTH=1280`, `STREAM_HEIGHT=720`, `DEFAULT_RTSP_URL=""`
- Room model already has `camera_endpoint` column -- used as first priority, `DEFAULT_RTSP_URL` as fallback
- One RTSP `cv2.VideoCapture` per room, shared across WebSocket viewers
- `LiveStreamService._active_streams` is class-level dict (shared across instances)
- MediaPipe face detection lazy-initialized; FaceNet/FAISS lazy-checked; graceful degradation if unavailable
- Detection enrichment (user name/student_id) requires DB session -- done at router layer via `enrich_detections()`
- `mediapipe>=0.10.14` added to requirements.txt
- Router mounted in main.py BEFORE websocket router

## Files NOT to Touch
- face.py, websocket.py routers - handled by another agent
- Database/migration files
