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

## Face-Related Codes
- `VALIDATION_ERROR`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `NOT_REGISTERED`
- `EMBEDDING_ERROR`
- `INDEX_SYNC_ERROR`
- `SERVER_ERROR`

## Status Mapping
| Status | Typical Face Module Scenario |
|---|---|
| 400 | Invalid image payload or validation failure |
| 401 | Missing/invalid Supabase JWT (register, status) or missing/invalid API key (recognize) |
| 403 | User inactive or email not confirmed (register, status) |
| 404 | Registration not found (where applicable) |
| 500 | Model inference/index sync/server error |

## Error Scenarios by Function

### FUN-03-01 (POST /face/register)
- `401 UNAUTHORIZED`: Missing or invalid Supabase JWT.
- `403 FORBIDDEN`: User `is_active = false` or `email_confirmed_at IS NULL`.
- `400 VALIDATION_ERROR`: Image count < 3 or > 5, no face detected, multiple faces, blur, too small.
- `500 SERVER_ERROR`: Unexpected server failure.

### FUN-03-02 (embedding generation — internal)
- `500 EMBEDDING_ERROR`: FaceNet inference failure.

### FUN-03-03 (storage sync — internal)
- `500 INDEX_SYNC_ERROR`: FAISS write or DB persistence failure.

### FUN-03-04 (POST /face/recognize)
- `401 UNAUTHORIZED`: Missing or invalid API key (`X-API-Key`).
- `400 VALIDATION_ERROR`: Invalid image payload.
- `500 SERVER_ERROR`: Model or index processing failure.

### FUN-03-05 (GET /face/status)
- `401 UNAUTHORIZED`: Missing or invalid Supabase JWT.
- `500 SERVER_ERROR`: Registration lookup failure.
