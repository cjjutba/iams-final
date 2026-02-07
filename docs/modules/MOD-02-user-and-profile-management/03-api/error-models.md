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

## User-Related Codes
- `VALIDATION_ERROR`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `NOT_FOUND`
- `CONFLICT`
- `SERVER_ERROR`

## Status Mapping
| Status | Typical User/Profile Scenario |
|---|---|
| 400 | Invalid payload or query params |
| 401 | Missing or invalid bearer token |
| 403 | Unauthorized role/action |
| 404 | User ID not found |
| 409 | Lifecycle conflict on delete/deactivate |
| 500 | Unexpected server error |
