# Endpoint Contract: GET /api/v1/schedules

## Function Mapping
- `FUN-05-01`

## Purpose
List schedules using day/filter query.

## Auth
- Requires Supabase JWT (`Authorization: Bearer <token>`).
- All roles (student, faculty, admin).

## Request
Query params:
- `day` (INTEGER 0-6, optional): Filter by `day_of_week` (0=Sunday, 1=Monday, ..., 6=Saturday).
- `room_id` (UUID, optional): Filter by room.
- `faculty_id` (UUID, optional): Filter by faculty.
- `active_only` (BOOLEAN, optional, default=true): Filter by `is_active=true`.

## Success Response
```json
{
  "success": true,
  "data": [
    {
      "id": "323e4567-e89b-12d3-a456-426614174000",
      "subject_code": "CS101",
      "subject_name": "Programming 1",
      "faculty_name": "Dr. Santos",
      "room": "Room 301",
      "day_of_week": 1,
      "start_time": "08:00:00",
      "end_time": "10:00:00",
      "is_active": true
    }
  ],
  "message": ""
}
```

## Sort Order
Results sorted by `day_of_week` ASC, `start_time` ASC.

## Error Cases
- `400`: invalid query filter (e.g., `day=9`)
- `401`: missing/invalid Supabase JWT
- `500`: server error
