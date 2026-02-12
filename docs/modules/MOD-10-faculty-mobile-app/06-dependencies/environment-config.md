# Environment Config

## Mobile Variables
| Variable | Description | Default |
|---|---|---|
| `API_BASE_URL` | Backend API base URL | `http://localhost:8000/api/v1` |
| `WS_BASE_URL` | WebSocket base URL | `ws://localhost:8000/api/v1` |
| `AUTH_STORAGE_KEY` | Secure storage key namespace | `iams_auth` |
| `ROLE_EXPECTED` | Route guard hint for faculty-only stack | `faculty` |
| `TIMEZONE` | Display timezone for all timestamps | `Asia/Manila` |

## Environment-Specific Values
| Variable | Development | Production |
|---|---|---|
| `API_BASE_URL` | `http://localhost:8000/api/v1` | `https://<domain>/api/v1` |
| `WS_BASE_URL` | `ws://localhost:8000/api/v1` | `wss://<domain>/api/v1` |

## WebSocket Config
| Setting | Value |
|---|---|
| Initial reconnect delay | 1000ms |
| Max reconnect delay | 30000ms |
| Backoff multiplier | 2x |
| Max reconnect attempts | Unlimited (with backoff) |

## Security Rules
1. Never commit real tokens or credentials to version control.
2. Use `https://` and `wss://` in production.
3. Store tokens in Expo SecureStore only (not AsyncStorage, not environment variables).
4. Mobile does NOT need `SUPABASE_URL` or `SUPABASE_ANON_KEY` — all auth via backend JWT.

## Validation Checklist
- [ ] `API_BASE_URL` resolves and responds to health check.
- [ ] `WS_BASE_URL` accepts WebSocket upgrade with valid JWT.
- [ ] `AUTH_STORAGE_KEY` is consistent across app.
- [ ] `TIMEZONE` is set to `Asia/Manila`.
- [ ] Production URLs use HTTPS/WSS.
- [ ] No Supabase client SDK variables configured (mobile uses backend JWT only).
