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

## Edge-Ingestion Codes
- `VALIDATION_ERROR`
- `UNAUTHORIZED`
- `NETWORK_ERROR`
- `QUEUE_OVERFLOW`
- `SERVER_ERROR`

## Status Mapping
| Status | Typical Edge Scenario |
|---|---|
| 400 | malformed payload, missing fields, invalid image |
| 401 | auth failure when endpoint protected |
| 500 | backend processing failure |
