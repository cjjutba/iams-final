# Environment Config

## Mobile Variables (Recommended)
| Variable | Description | Default |
|---|---|---|
| `API_BASE_URL` | Backend API base URL | `http://localhost:8000/api/v1` |
| `WS_BASE_URL` | WebSocket base URL | `ws://localhost:8000/api/v1` |
| `SUPABASE_URL` | Supabase project URL (if used in mobile auth) | - |
| `SUPABASE_ANON_KEY` | Supabase anon key for client auth | - |
| `AUTH_STORAGE_KEY` | Key prefix for secure token storage | `iams_auth` |

## Runtime Config Rules
- Use environment-specific API/WS URLs.
- Use `https://` and `wss://` in production.
- Keep auth/session timeouts aligned with backend token policy.
