# Endpoint Contract: GET /schedules/me

## Function Mapping
- `FUN-05-04`

## Purpose
Return schedules for current authenticated user context.

## Success Response
```json
{
  "success": true,
  "data": []
}
```

## Behavior Notes
- Student: schedules from enrollments.
- Faculty: schedules by `faculty_id`.

## Error Cases
- `401`: missing/invalid token
- `403`: unsupported role context
- `500`: server error
