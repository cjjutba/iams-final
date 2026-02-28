# Supabase Client Operation: Token Refresh

## Function Mapping
- `FUN-01-04`

## Implementation
**Not a backend endpoint.** Token refresh is handled automatically by Supabase client SDK on mobile.

## Supabase SDK Call
```typescript
// Automatic — Supabase client refreshes when access token expires
// Manual call if needed:
const { data, error } = await supabase.auth.refreshSession()
```

## Supabase Session Response
```json
{
  "access_token": "new_supabase_jwt",
  "refresh_token": "new_refresh_token",
  "token_type": "bearer",
  "expires_in": 1800
}
```

## Token Lifetimes
- Access token expiry: 30 minutes (configurable in Supabase project settings)
- Refresh token expiry: 7 days (Supabase default)

## Error Cases
- Expired/invalid refresh token: Supabase returns error; mobile redirects to login screen.

## Caller Context
- Automatic refresh handling in Supabase client session management.
- Mobile auth layer should handle `onAuthStateChange` events from Supabase client.
