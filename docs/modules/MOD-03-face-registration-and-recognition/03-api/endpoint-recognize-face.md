# Endpoint Contract: POST /face/recognize

## Function Mapping
- `FUN-03-04`

## Purpose
Recognize single cropped face against registered embeddings.

## Auth
- **API key required.** Header: `X-API-Key: <edge_api_key>`
- Validated against `EDGE_API_KEY` env variable.
- No Supabase JWT — this endpoint is called by edge devices (RPi) that do not hold user JWTs.

## Request
Multipart form-data:
- `image`: File (cropped face image — any size; backend resizes to 160x160)
- `room_id`: string

## Processing
1. Validate API key.
2. Validate image payload.
3. Resize face crop to 160x160 RGB (model input size).
4. Generate embedding via FaceNet.
5. Search FAISS top-1 neighbor.
6. Compare against threshold (`RECOGNITION_THRESHOLD`, default 0.6).

## Success Response (Matched)
```json
{
  "success": true,
  "data": {
    "matched": true,
    "user_id": "uuid",
    "confidence": 0.85,
    "student_name": "Juan Dela Cruz"
  }
}
```

## Success Response (No Match)
```json
{
  "success": true,
  "data": {
    "matched": false,
    "user_id": null,
    "confidence": 0.0
  }
}
```

## Error Cases
- `400`: invalid image payload
- `401`: missing/invalid API key
- `500`: model/index processing failure

## Caller Context
- Edge recognition pipeline (RPi) and internal processing services.
