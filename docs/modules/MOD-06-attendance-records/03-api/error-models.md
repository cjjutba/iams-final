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

## Attendance-Related Codes
- `VALIDATION_ERROR`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `NOT_FOUND`
- `CONFLICT`
- `SERVER_ERROR`

## Status Mapping
| Status | Typical Attendance Scenario |
|---|---|
| 400 | invalid date/status/payload |
| 401 | missing/invalid token |
| 403 | unauthorized role/action |
| 404 | attendance target/schedule not found |
| 409 | conflict in manual update/upsert policy |
| 500 | unexpected server error |
