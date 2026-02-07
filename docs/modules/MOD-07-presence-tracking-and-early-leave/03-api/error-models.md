# Error Models

## Standard Error Shape
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": []
  }
}
```

## Presence-Related Codes
- `VALIDATION_ERROR`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `NOT_FOUND`
- `THRESHOLD_CONFIG_ERROR`
- `SERVER_ERROR`

## Status Mapping
| Status | Typical Presence Scenario |
|---|---|
| 400 | invalid attendance_id/date/schedule filters |
| 401 | missing/invalid token |
| 403 | unauthorized role/action |
| 404 | attendance/schedule context not found |
| 500 | unexpected service error |
