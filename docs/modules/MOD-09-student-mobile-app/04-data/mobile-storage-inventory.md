# Mobile Storage Inventory

## Secure Storage (Required — Expo SecureStore)
| Key | Contents | Retention | Auth Context |
|---|---|---|---|
| `access_token` | Current access JWT | Until logout/expiry | Post-auth |
| `refresh_token` | Refresh token | Until logout/revoke | Post-auth |
| `user_id` | Authenticated user identifier (UUID) | Until logout | Post-auth |

## Non-Sensitive Storage (AsyncStorage)
| Key | Contents | Retention | Auth Context |
|---|---|---|---|
| `first_launch` | Boolean flag for onboarding | Permanent | Pre-auth |
| `attendance_cache` | Last known attendance list | Until refresh or logout | Post-auth |
| `schedule_cache` | Last known schedule data | Until refresh or logout | Post-auth |
| `notification_cache` | Recent feed items | Until refresh or logout | Post-auth |

## Security Rules
1. Never store plaintext passwords in any storage.
2. Never store tokens in AsyncStorage — only in SecureStore.
3. Never log token values, passwords, or sensitive user data to console.
4. Clear all secure and cached entries on logout.
5. Token validation before use — if expired, trigger refresh flow.
6. Mobile does NOT store Supabase credentials — all auth goes through backend API.
