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

## Auth-Related Codes
- `VALIDATION_ERROR`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `NOT_FOUND`
- `SERVER_ERROR`

## Status Mapping
| Status | Typical Auth Scenario |
|---|---|
| 400 | Invalid request body / malformed fields |
| 401 | Invalid credentials or token |
| 403 | Role restriction or inactive account |
| 404 | User not found |
| 500 | Unexpected server error |
