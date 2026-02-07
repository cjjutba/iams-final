# Endpoint Contract: GET /attendance/me?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD

## Function Mapping
- `FUN-06-03`

## Success Response
```json
{
  "success": true,
  "data": [
    {
      "date": "2024-01-15",
      "schedule": {},
      "status": "present",
      "check_in_time": "08:05:00",
      "presence_score": 95.5
    }
  ]
}
```

## Error Cases
- `400`: invalid date filters
- `401`: missing/invalid token
- `403`: unauthorized role/policy
