# API Inventory

## Base
- Backend URL: configured via `EDGE_SERVER_URL`
- Primary contract endpoint: `POST /face/process`
- Base path prefix: `/api/v1` (assumed in all endpoint paths below)

## Auth Context
Edge device authenticates using a shared API key sent in the `X-API-Key` header. Backend validates against `EDGE_API_KEY` environment variable. Edge does NOT use Supabase JWT.

## Endpoint List
| Method | Path | Function ID | Caller | Auth |
|---|---|---|---|---|
| POST | `/face/process` | FUN-04-03, FUN-04-04, FUN-04-05 | edge runtime | API key (`X-API-Key` header) |

## Request Contract Summary
- `room_id`: string UUID
- `timestamp`: ISO 8601 string
- `faces[]`: list of face objects
- `faces[].image`: base64 JPEG (~112x112 crop, any size accepted; backend resizes to 160x160)
- `faces[].bbox`: optional `[x, y, w, h]`

## Response Contract Summary (Success Envelope)
```json
{
  "success": true,
  "data": {
    "processed": 3,
    "matched": [
      {"user_id": "uuid", "confidence": 0.85}
    ],
    "unmatched": 1
  },
  "message": "Processed 3 faces; 2 matched, 1 unmatched"
}
```

## Error Envelope
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```
