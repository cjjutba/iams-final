# Endpoint Contract: GET /presence/{attendance_id}/logs

## Function Mapping
- `FUN-07-06`

## Success Response
```json
{
  "success": true,
  "data": [
    {
      "scan_number": 1,
      "scan_time": "08:05:00",
      "detected": true,
      "confidence": 0.92
    }
  ]
}
```

## Error Cases
- `400`: invalid attendance_id
- `401`: missing/invalid token
- `403`: unauthorized role/access
- `404`: attendance not found
