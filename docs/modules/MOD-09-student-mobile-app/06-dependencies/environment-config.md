# Environment Config

## Mobile Variables
| Variable | Description | Default | Required |
|---|---|---|---|
| `API_BASE_URL` | Backend API base URL | `http://localhost:8000/api/v1` | Yes |
| `WS_BASE_URL` | WebSocket base URL | `ws://localhost:8000/api/v1` | Yes |
| `AUTH_STORAGE_KEY` | Key prefix for secure token storage | `iams_auth` | Yes |
| `TIMEZONE` | Display timezone for timestamps | `Asia/Manila` | No (default) |

## Environment-Specific Values
| Variable | Development | Production |
|---|---|---|
| `API_BASE_URL` | `http://localhost:8000/api/v1` | `https://<host>/api/v1` |
| `WS_BASE_URL` | `ws://localhost:8000/api/v1` | `wss://<host>/api/v1` |

## WebSocket Config (Optional)
| Variable | Description | Default |
|---|---|---|
| `WS_RECONNECT_BASE_DELAY_MS` | Initial reconnect delay | `1000` |
| `WS_RECONNECT_MAX_DELAY_MS` | Max reconnect delay (exponential backoff cap) | `30000` |

## Configuration Rules
1. Use environment-specific API/WS URLs — never hardcode.
2. Use `https://` and `wss://` in production.
3. Keep auth/session timeouts aligned with backend token policy.
4. Mobile does NOT need `SUPABASE_URL` or `SUPABASE_ANON_KEY` — all auth goes through backend API.

## Security Rules
1. Never commit tokens, passwords, or API keys to source code.
2. Use `.env` files with proper `.gitignore` entries.
3. JWT tokens stored in Expo SecureStore only — never in environment files.

## Validation Checklist
- [ ] `API_BASE_URL` resolves and returns 200 on health check.
- [ ] `WS_BASE_URL` accepts WebSocket upgrade.
- [ ] Backend auth endpoints respond correctly (login, register, refresh).
- [ ] Post-auth endpoints reject requests without JWT (401).
- [ ] WebSocket rejects connections without valid `token` query param (close code 4001).
- [ ] Timestamps in API responses use +08:00 offset.
