# Endpoint Contract: POST /attendance/manual

## Function Mapping
- `FUN-06-05`

## Request
```json
{
  "student_id": "uuid",
  "schedule_id": "uuid",
  "date": "2024-01-15",
  "status": "present",
  "remarks": "System was down"
}
```

## Success Response
```json
{
  "success": true,
  "data": {}
}
```

## Error Cases
- `400`: invalid payload/status
- `401`: missing/invalid token
- `403`: student/non-faculty caller
- `404`: referenced student/schedule not found
