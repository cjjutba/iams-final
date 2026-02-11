# Endpoint Contract: POST /face/register

## Function Mapping
- `FUN-03-01`
- `FUN-03-02`
- `FUN-03-03`

## Purpose
Validate registration images, generate embeddings, and store synchronized mapping.

## Auth
- **Supabase JWT required.** Header: `Authorization: Bearer <supabase_jwt>`
- User ID extracted from JWT `sub` claim.
- Backend verifies `is_active = true` and `email_confirmed_at IS NOT NULL`.

## Request
Multipart form-data:
- `images`: File[] (3-5 face images)

## Success Response
```json
{
  "success": true,
  "data": {
    "embedding_id": "uuid",
    "registered_at": "2026-01-15T10:00:00Z"
  },
  "message": "Face registration successful"
}
```

## Error Cases
- `400`: invalid image set (count/quality/face detection)
- `401`: missing/invalid Supabase JWT
- `403`: inactive user or unconfirmed email
- `500`: embedding generation or storage sync failure

## Caller Screens
- `SCR-009` StudentRegisterStep3Screen
- `SCR-017` StudentFaceReregisterScreen
