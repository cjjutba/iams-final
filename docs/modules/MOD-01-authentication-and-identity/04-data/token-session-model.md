# Token and Session Model

## Token Types
- Access Token: short-lived JWT for protected endpoints.
- Refresh Token: long-lived token for renewing access token.

## Lifetime Targets
- Access token expiry: 30 minutes (configurable).
- Refresh token expiry: 7 days (Supabase-based flow).

## Session Flow
1. Login issues access + refresh token pair.
2. Client attaches access token on protected requests.
3. On access token expiry, client calls refresh endpoint.
4. If refresh fails, user must re-authenticate.

## Security Controls
- Tokens transmitted over HTTPS in production.
- Token secrets/keys stored in environment variables only.
- Expired/invalid tokens return `401`.
