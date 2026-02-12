# Endpoint Contract: POST /api/v1/schedules

## Function Mapping
- `FUN-05-03`

## Purpose
Create new schedule (admin-only).

## Auth
- Requires Supabase JWT (`Authorization: Bearer <token>`).
- Requires `role == "admin"`. Non-admin callers receive `403`.

## Request
```json
{
  "subject_code": "CS101",
  "subject_name": "Programming 1",
  "faculty_id": "123e4567-e89b-12d3-a456-426614174000",
  "room_id": "223e4567-e89b-12d3-a456-426614174000",
  "day_of_week": 1,
  "start_time": "08:00:00",
  "end_time": "10:00:00",
  "semester": "1st Sem",
  "academic_year": "2025-2026"
}
```

### Field Details
- `subject_code` (VARCHAR(20), required): Course code.
- `subject_name` (VARCHAR(255), required): Course name.
- `faculty_id` (UUID, required): FK to `users` table. Must reference user with `role == "faculty"`.
- `room_id` (UUID, required): FK to `rooms` table.
- `day_of_week` (INTEGER 0-6, required): 0=Sunday, 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday, 6=Saturday.
- `start_time` (TIME, required): Must be earlier than `end_time`.
- `end_time` (TIME, required): Must be later than `start_time`.
- `semester` (VARCHAR(20), optional): Term metadata.
- `academic_year` (VARCHAR(20), optional): Year metadata.

## Success Response
```json
{
  "success": true,
  "data": {
    "id": "323e4567-e89b-12d3-a456-426614174000",
    "subject_code": "CS101",
    "subject_name": "Programming 1",
    "faculty_id": "123e4567-e89b-12d3-a456-426614174000",
    "room_id": "223e4567-e89b-12d3-a456-426614174000",
    "day_of_week": 1,
    "start_time": "08:00:00",
    "end_time": "10:00:00",
    "semester": "1st Sem",
    "academic_year": "2025-2026",
    "is_active": true,
    "created_at": "2026-02-12T14:30:00Z"
  },
  "message": "Schedule created successfully"
}
```

## Error Cases
- `400`: invalid payload/time values/references (`start_time >= end_time`, invalid FKs)
- `401`: missing/invalid Supabase JWT
- `403`: non-admin caller
- `500`: server error
