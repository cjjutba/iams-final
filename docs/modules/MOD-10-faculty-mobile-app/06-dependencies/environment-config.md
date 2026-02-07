# Environment Config

## Mobile Variables (Recommended)
| Variable | Description | Default |
|---|---|---|
| `API_BASE_URL` | Backend API base URL | `http://localhost:8000/api/v1` |
| `WS_BASE_URL` | WebSocket base URL | `ws://localhost:8000/api/v1` |
| `AUTH_STORAGE_KEY` | Secure storage key namespace | `iams_auth` |
| `ROLE_EXPECTED` | Route guard hint for faculty-only stack | `faculty` |

## Runtime Rules
- Use environment-specific URLs for development/pilot/production.
- Use `https://` and `wss://` in production.
- Keep auth timeout/retry policy aligned with backend token settings.
