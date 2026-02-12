# Endpoint Contract: GET /api/v1/schedules/me

## Function Mapping
- `FUN-05-04`

## Purpose
Return schedules for current authenticated user, scoped by role.

## Auth
- Requires Supabase JWT (`Authorization: Bearer <token>`).
- Scoped by JWT `sub` (user ID) and `role` claim.

## Behavior
- **Faculty**: Returns schedules WHERE `faculty_id` matches JWT `sub` AND `is_active=true`. Faculty sees only their own teaching schedules.
- **Student**: Returns schedules via enrollments WHERE `student_id` matches JWT `sub` AND schedule `is_active=true`. Student sees only their enrolled schedules.
- **Admin**: Returns all active schedules (or admin's teaching schedules if admin also teaches).

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
- `401`: missing/invalid Supabase JWT
- `403`: unsupported role context
- `500`: server error
