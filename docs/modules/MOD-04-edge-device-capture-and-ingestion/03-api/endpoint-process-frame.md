# Endpoint Contract: POST /face/process

## Function Mapping
- `FUN-04-03`
- `FUN-04-04`
- `FUN-04-05`

## Purpose
Send one or more cropped faces from edge runtime to backend for processing.

## Request (application/json)
```json
{
  "room_id": "uuid",
  "faces": [
    {
      "image": "base64_encoded_jpeg",
      "bbox": [x, y, width, height]
    }
  ],
  "timestamp": "2024-01-15T10:00:00Z"
}
```

## Success Response
```json
{
  "success": true,
  "data": {
    "processed": 3,
    "matched": [
      {"user_id": "uuid", "confidence": 0.85},
      {"user_id": "uuid", "confidence": 0.92}
    ],
    "unmatched": 1
  }
}
```

## Error Cases
- `400`: invalid payload schema/image
- `401`: missing/invalid auth (if protected)
- `500`: server/recognition error

## Caller Context
- Edge runtime sender and retry worker.
