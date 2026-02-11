# Endpoint Contract: GET /face/status

## Function Mapping
- `FUN-03-05`

## Purpose
Return current user face registration state.

## Auth
- **Supabase JWT required.** Header: `Authorization: Bearer <supabase_jwt>`
- User ID extracted from JWT `sub` claim.

## Success Response
```json
{
  "success": true,
  "data": {
    "registered": true,
    "registered_at": "2026-01-15T10:00:00Z"
  }
}
```

## Success Response (Not Registered)
```json
{
  "success": true,
  "data": {
    "registered": false,
    "registered_at": null
  }
}
```

## Error Cases
- `401`: missing/invalid Supabase JWT
- `500`: registration lookup failure

## Caller Screens
- `SCR-009` StudentRegisterStep3Screen
- `SCR-017` StudentFaceReregisterScreen
