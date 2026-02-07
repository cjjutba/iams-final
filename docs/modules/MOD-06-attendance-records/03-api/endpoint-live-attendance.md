# Endpoint Contract: GET /attendance/live/{schedule_id}

## Function Mapping
- `FUN-06-06`

## Success Response
```json
{
  "success": true,
  "data": {
    "session_active": true,
    "started_at": "08:00:00",
    "current_scan": 15,
    "students": [
      {
        "id": "uuid",
        "name": "Juan Dela Cruz",
        "status": "present",
        "last_seen": "08:45:00",
        "consecutive_misses": 0
      }
    ]
  }
}
```

## Error Cases
- `401`: missing/invalid token
- `403`: unauthorized role
- `404`: schedule not found
