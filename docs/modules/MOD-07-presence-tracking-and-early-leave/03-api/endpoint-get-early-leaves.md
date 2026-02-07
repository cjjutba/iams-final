# Endpoint Contract: GET /presence/early-leaves?schedule_id=uuid&date=YYYY-MM-DD

## Function Mapping
- `FUN-07-06`

## Success Response
```json
{
  "success": true,
  "data": [
    {
      "student_id": "uuid",
      "student_name": "Juan Dela Cruz",
      "detected_at": "09:30:00",
      "consecutive_misses": 3
    }
  ]
}
```

## Error Cases
- `400`: invalid schedule/date filters
- `401`: missing/invalid token
- `403`: unauthorized role/access
- `404`: schedule not found (policy-dependent)
