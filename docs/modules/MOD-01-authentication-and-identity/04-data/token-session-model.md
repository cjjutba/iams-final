# Token and Session Model

## Auth Provider
**Supabase Auth** is the chosen authentication provider.

## Token Types
- **Access Token:** Supabase-issued JWT (short-lived) used for all protected backend endpoints.
- **Refresh Token:** Supabase-managed long-lived token for renewing access tokens.

## JWT Structure (Supabase-Issued)
| Claim | Description |
|---|---|
| `sub` | User ID (UUID) — maps to `users.id` in local DB |
| `email` | User's email address |
| `role` | Supabase role (not IAMS role; IAMS role is in local `users` table) |
| `aud` | Audience (Supabase project reference) |
| `exp` | Expiration timestamp |
| `iat` | Issued at timestamp |
| `iss` | Issuer (Supabase project URL) |

## Lifetime Targets
- Access token expiry: 30 minutes (configurable in Supabase project settings).
- Refresh token expiry: 7 days (Supabase default).

## Session Flow
1. **Registration:** Backend creates Supabase Auth user via Admin API; Supabase sends email verification.
2. **Email Verification:** User clicks link in email; Supabase marks email as confirmed.
3. **Login:** Mobile calls `supabase.auth.signInWithPassword()`; Supabase returns access + refresh token pair.
4. **API Calls:** Mobile sends Supabase JWT in `Authorization: Bearer` header; backend verifies JWT and checks is_active + email_confirmed.
5. **Token Refresh:** Supabase client automatically calls `refreshSession()` when access token expires.
6. **Session Expiry:** If refresh token expires, Supabase client fires `onAuthStateChange(SIGNED_OUT)`; mobile redirects to login.

## Backend JWT Verification
1. Extract JWT from `Authorization: Bearer <token>` header.
2. Verify JWT signature using Supabase JWT secret (from `SUPABASE_JWT_SECRET` env var).
3. Check `exp` claim is not expired.
4. Extract `sub` claim as user ID.
5. Load user from local `users` table by ID.
6. Check `is_active = true` and `email_confirmed_at IS NOT NULL`.
7. Attach user context to request for downstream use.

## Mobile Token Storage
- Supabase client SDK handles token storage automatically.
- Tokens are persisted using the configured storage adapter (AsyncStorage or SecureStore).
- On app startup, Supabase client restores session from storage.

## Security Controls
- Tokens transmitted over HTTPS in production.
- JWT secret stored in environment variables only (never in source code).
- Expired/invalid tokens return `401`.
- Inactive or email-unverified users return `403`.
- Tokens are never logged or exposed in error messages.
