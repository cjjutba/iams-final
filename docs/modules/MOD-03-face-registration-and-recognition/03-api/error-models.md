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

## Face-Related Codes
- `VALIDATION_ERROR`
- `UNAUTHORIZED`
- `NOT_REGISTERED`
- `EMBEDDING_ERROR`
- `INDEX_SYNC_ERROR`
- `SERVER_ERROR`

## Status Mapping
| Status | Typical Face Module Scenario |
|---|---|
| 400 | Invalid image payload or validation failure |
| 401 | Missing/invalid auth token on protected routes |
| 404 | Registration not found (where applicable) |
| 500 | Model inference/index sync/server error |
