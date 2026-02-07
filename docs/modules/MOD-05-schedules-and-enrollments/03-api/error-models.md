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

## Schedule-Related Codes
- `VALIDATION_ERROR`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `NOT_FOUND`
- `CONFLICT`
- `SERVER_ERROR`

## Status Mapping
| Status | Typical Schedule Scenario |
|---|---|
| 400 | invalid day/time/payload fields |
| 401 | missing or invalid bearer token |
| 403 | unauthorized role/action |
| 404 | schedule not found |
| 409 | conflict (if overlap/constraint policy enforced) |
| 500 | unexpected server error |
