# Mobile Storage Inventory

## Secure Storage (Required)
| Key | Contents | Retention |
|---|---|---|
| `access_token` | current access token | until logout/expiry |
| `refresh_token` | refresh token (if used) | until logout/revoke |
| `user_id` | authenticated user identifier | until logout |

## Optional Cached Storage
| Key | Contents | Purpose |
|---|---|---|
| `attendance_cache` | last known attendance list | offline display fallback |
| `schedule_cache` | last known schedule data | faster startup display |
| `notification_cache` | recent feed items | preserve UX on reconnect |

## Security Rules
- Never store plaintext password.
- Do not log token values.
- Clear secure and cached entries on logout.
