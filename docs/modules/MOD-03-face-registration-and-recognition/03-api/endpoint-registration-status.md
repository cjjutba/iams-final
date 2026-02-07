# Endpoint Contract: GET /face/status

## Function Mapping
- `FUN-03-05`

## Purpose
Return current user face registration state.

## Success Response
```json
{
  "success": true,
  "data": {
    "registered": true,
    "registered_at": "2024-01-15T10:00:00Z"
  }
}
```

## Error Cases
- `401`: missing/invalid token
- `500`: registration lookup failure

## Caller Screens
- `SCR-009` StudentRegisterStep3Screen
- `SCR-017` StudentFaceReregisterScreen
