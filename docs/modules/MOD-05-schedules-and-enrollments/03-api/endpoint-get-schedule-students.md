# Endpoint Contract: GET /api/v1/schedules/{id}/students

## Function Mapping
- `FUN-05-05`

## Purpose
Return roster (enrolled students) for one schedule.

## Auth
- Requires Supabase JWT (`Authorization: Bearer <token>`).
- Restricted to:
  - **Admin**: full access to all rosters.
  - **Faculty**: only if `schedule.faculty_id` matches JWT `sub`.
  - **Student**: only if student has an enrollment record for this schedule.

## Path Parameter
- `id` (UUID): Schedule ID.

## Success Response
```json
{
  "success": true,
  "data": [
    {
      "id": "423e4567-e89b-12d3-a456-426614174000",
      "student_id": "21-A-02177",
      "first_name": "Juan",
      "last_name": "Dela Cruz"
    }
  ],
  "message": ""
}
```

### Response Field Details
- `id`: `users.id` (UUID) — the student's user ID.
- `student_id`: `users.student_id` (VARCHAR) — the school-issued student ID (e.g., "21-A-02177").
- `first_name`: `users.first_name`.
- `last_name`: `users.last_name`.

## Error Cases
- `401`: missing/invalid Supabase JWT
- `403`: caller not authorized (not admin, not assigned faculty, not enrolled student)
- `404`: schedule not found
- `500`: server error
