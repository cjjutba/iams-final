# Endpoint Contract: GET /api/v1/schedules/{id}

## Function Mapping
- `FUN-05-02`

## Purpose
Return one schedule by ID with full details.

## Auth
- Requires Supabase JWT (`Authorization: Bearer <token>`).
- All roles.

## Path Parameter
- `id` (UUID)

## Success Response
```json
{
  "success": true,
  "data": {
    "id": "323e4567-e89b-12d3-a456-426614174000",
    "subject_code": "CS101",
    "subject_name": "Programming 1",
    "faculty_id": "123e4567-e89b-12d3-a456-426614174000",
    "faculty_name": "Dr. Santos",
    "room_id": "223e4567-e89b-12d3-a456-426614174000",
    "room": "Room 301",
    "day_of_week": 1,
    "start_time": "08:00:00",
    "end_time": "10:00:00",
    "semester": "1st Sem",
    "academic_year": "2025-2026",
    "is_active": true,
    "created_at": "2026-02-01T08:00:00Z"
  },
  "message": ""
}
```

## Error Cases
- `401`: missing/invalid Supabase JWT
- `404`: schedule not found
- `500`: server error
