# Mobile Storage Inventory

## Secure Storage (Required)
| Key | Contents | Retention |
|---|---|---|
| `access_token` | current access token | until logout/expiry |
| `refresh_token` | refresh token (if used) | until logout/revoke |
| `user_id` | authenticated faculty user ID | until logout |
| `role` | role hint for route restore | until logout |

## Optional Cached Storage
| Key | Contents | Purpose |
|---|---|---|
| `faculty_schedule_cache` | schedule snapshot | faster startup |
| `live_attendance_cache` | last live roster snapshot | reconnect UX continuity |
| `faculty_notifications_cache` | recent events | feed continuity |

## Security Rules
- Never store plaintext password.
- Never log token values.
- Clear secure and cached entries on logout.
