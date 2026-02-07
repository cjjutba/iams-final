# Endpoint Contract: GET /attendance/today?schedule_id=uuid

## Function Mapping
- `FUN-06-02`

## Success Response
```json
{
  "success": true,
  "data": {
    "schedule": {},
    "records": [
      {
        "student_id": "uuid",
        "student_name": "Juan Dela Cruz",
        "status": "present",
        "check_in_time": "08:05:00",
        "presence_score": 95.5
      }
    ],
    "summary": {
      "total": 30,
      "present": 28,
      "late": 1,
      "absent": 1
    }
  }
}
```

## Error Cases
- `400`: missing/invalid schedule_id
- `401`: missing/invalid token
- `403`: unauthorized role
- `404`: schedule not found
