# Endpoint Contract: POST /face/recognize

## Function Mapping
- `FUN-03-04`

## Purpose
Recognize single cropped face against registered embeddings.

## Request
Multipart form-data:
- `image`: File (cropped face image)
- `room_id`: string

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
- `500`: model/index processing failure

## Caller Context
- Edge recognition pipeline and internal processing services.
