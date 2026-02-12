# Mobile Storage Inventory

## Secure Storage (Expo SecureStore)
| Key | Auth Context | Contents | Retention |
|---|---|---|---|
| `access_token` | Post-auth | Current access JWT | Until logout/expiry |
| `refresh_token` | Post-auth | Refresh JWT | Until logout/revoke |
| `user_id` | Post-auth | Authenticated faculty user ID | Until logout |
| `role` | Post-auth | Role hint for route restore (`faculty`) | Until logout |

## Non-Sensitive Storage (AsyncStorage)
| Key | Auth Context | Contents | Purpose |
|---|---|---|---|
| `faculty_schedule_cache` | Post-auth | Schedule snapshot | Faster startup |
| `live_attendance_cache` | Post-auth | Last live roster snapshot | Reconnect UX continuity |
| `faculty_notifications_cache` | Post-auth | Recent events | Feed continuity |

## Security Rules
1. Never store plaintext password.
2. Never log token values.
3. Store tokens ONLY in Expo SecureStore (never AsyncStorage).
4. Clear both SecureStore and AsyncStorage cached entries on logout.
5. Do not expose token values in URL paths (WebSocket uses query param `token` only).
6. Wipe all auth state on session invalidation or 401 refresh failure.
