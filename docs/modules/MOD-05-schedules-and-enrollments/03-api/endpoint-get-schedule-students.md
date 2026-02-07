# Endpoint Contract: GET /schedules/{id}/students

## Function Mapping
- `FUN-05-05`

## Purpose
Return roster (enrolled students) for one schedule.

## Success Response
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "student_id": "2024-0001",
      "name": "Juan Dela Cruz"
    }
  ]
}
```

## Error Cases
- `401`: missing/invalid token
- `403`: unauthorized role/access
- `404`: schedule not found
- `500`: server error
