# Endpoint Contract: POST /auth/refresh

## Function Mapping
- `FUN-01-04`

## Purpose
Refresh access token without forcing re-login.

## Request
```json
{
  "refresh_token": "refresh_token"
}
```

## Success Response
```json
{
  "success": true,
  "data": {
    "access_token": "new_jwt_token"
  }
}
```

## Error Cases
- `401`: invalid or expired refresh token
- `500`: token refresh service failure

## Caller Context
- Automatic refresh handling in mobile auth/session layer.
