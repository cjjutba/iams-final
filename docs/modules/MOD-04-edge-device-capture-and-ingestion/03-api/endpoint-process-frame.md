# Endpoint Contract: POST /face/process

## Function Mapping
- `FUN-04-03`
- `FUN-04-04`
- `FUN-04-05`

## Purpose
Send one or more cropped faces from edge runtime to backend for processing.

## Auth
- **Method:** Shared API key via `X-API-Key` header.
- **Validation:** Backend checks header against `EDGE_API_KEY` environment variable.
- **No Supabase JWT** — edge devices do not hold JWTs.

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
  "timestamp": "2026-01-15T10:00:00Z"
}
```

**Notes:**
- `faces[].image`: Base64-encoded JPEG at 70% quality. Crop size is ~112x112 from edge; backend handles resize to 160x160 for FaceNet.
- `faces[].bbox`: Optional bounding box metadata `[x, y, w, h]`.
- `timestamp`: ISO 8601 capture time.

## Processing (Backend Side)
1. Validate API key from `X-API-Key` header.
2. Validate payload schema (room_id, faces, timestamp).
3. Decode Base64 JPEG for each face.
4. Resize each crop to 160x160 (FaceNet model input).
5. Run recognition via MOD-03 service (FAISS search, threshold 0.6).
6. Return processed/matched/unmatched summary.

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
  },
  "message": "Processed 3 faces; 2 matched, 1 unmatched"
}
```

## Error Cases
- `400`: invalid payload schema, missing fields, or invalid image.
- `401`: missing or invalid `X-API-Key` header.
- `500`: server/recognition error.

## Caller Context
- Edge runtime sender and retry worker.
- Every request must include `X-API-Key` header.
