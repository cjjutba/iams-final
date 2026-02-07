# Endpoint Contract: POST /face/register

## Function Mapping
- `FUN-03-01`
- `FUN-03-02`
- `FUN-03-03`

## Purpose
Validate registration images, generate embeddings, and store synchronized mapping.

## Request
Multipart form-data:
- `images`: File[] (3-5 face images)

## Success Response
```json
{
  "success": true,
  "data": {
    "embedding_id": "uuid",
    "registered_at": "2024-01-15T10:00:00Z"
  }
}
```

## Error Cases
- `400`: invalid image set (count/quality/face detection)
- `401`: unauthorized user context
- `500`: embedding generation or storage sync failure

## Caller Screens
- `SCR-009` StudentRegisterStep3Screen
- `SCR-017` StudentFaceReregisterScreen
