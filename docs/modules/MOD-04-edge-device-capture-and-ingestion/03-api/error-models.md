# Error Models

## Standard Error Shape
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```

## Edge-Ingestion Error Codes
| Code | Description |
|---|---|
| `VALIDATION_ERROR` | Invalid payload schema, missing fields, bad image |
| `UNAUTHORIZED` | Missing or invalid `X-API-Key` header |
| `NETWORK_ERROR` | Edge-side: backend unreachable (triggers queue) |
| `QUEUE_OVERFLOW` | Edge-side: queue at max capacity, oldest dropped |
| `SERVER_ERROR` | Backend processing/recognition failure |

## Status Mapping
| Status | Scenario | Error Code |
|---|---|---|
| 400 | Malformed payload, missing fields, invalid image | `VALIDATION_ERROR` |
| 401 | Missing or invalid `X-API-Key` header | `UNAUTHORIZED` |
| 500 | Backend processing failure | `SERVER_ERROR` |

## Error Scenarios by Function
| Function | Error Scenario | Expected |
|---|---|---|
| FUN-04-03 | No `X-API-Key` header | 401 `UNAUTHORIZED` |
| FUN-04-03 | Invalid API key | 401 `UNAUTHORIZED` |
| FUN-04-03 | Malformed payload | 400 `VALIDATION_ERROR` |
| FUN-04-03 | Backend down | `NETWORK_ERROR` → queue |
| FUN-04-04 | Queue full | `QUEUE_OVERFLOW`, oldest dropped |
| FUN-04-05 | Retry with invalid key | 401 `UNAUTHORIZED` |
