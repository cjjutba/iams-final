# Environment Configuration

## Required Variables (Shared with Other Modules)
| Variable | Description | Default | Required By |
|---|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string (Supabase pooler, IPv4) | — | Backend (recipient resolution queries) |
| `SUPABASE_URL` | Supabase project URL | — | Backend (auth verification) |
| `SUPABASE_ANON_KEY` | Supabase anonymous/public key | — | Mobile (Supabase client SDK) |
| `JWT_SECRET_KEY` | Supabase JWT secret for token verification | — | Backend (WebSocket JWT verification) |
| `TIMEZONE` | System timezone for event timestamps | `Asia/Manila` | Backend (event timestamp formatting) |

## Backend Variables (MOD-08 Specific)
| Variable | Description | Default | Type |
|---|---|---|---|
| `WS_HEARTBEAT_INTERVAL` | Heartbeat ping interval in seconds | `30` | integer |
| `WS_STALE_TIMEOUT` | Time to mark connection stale after no pong (seconds) | `60` | integer |
| `WS_MAX_CONNECTIONS_PER_USER` | Safety cap on connections per user | `3` | integer |
| `WS_ENABLE_DELIVERY_LOGS` | Enable optional delivery logging | `false` | boolean |

## Mobile Variables (MOD-08 Specific)
| Variable | Description | Default | Type |
|---|---|---|---|
| `WS_BASE_URL` | WebSocket base URL | `ws://localhost:8000/api/v1` | string |
| `WS_RECONNECT_BASE_DELAY_MS` | Initial reconnect delay | `1000` | integer |
| `WS_RECONNECT_MAX_DELAY_MS` | Max reconnect delay (exponential backoff cap) | `10000` | integer |
| `WS_RECONNECT_MAX_ATTEMPTS` | Retry cap for reconnect loop (0 = infinite) | `0` | integer |

## Configuration Rules
- Keep mobile and backend URL/protocol aligned by environment.
- Use `wss://` in production over HTTPS.
- `WS_HEARTBEAT_INTERVAL` and `WS_STALE_TIMEOUT` must be positive integers.
- `WS_STALE_TIMEOUT` should be > `WS_HEARTBEAT_INTERVAL` (typically 2x).
- Invalid config (non-integer, negative) should fail fast at startup.

## Security Rules
- Never hardcode secrets in source code.
- Keep `.env.example` synchronized with runtime requirements.
- Production must use `wss://` (secure WebSocket over TLS).
- `JWT_SECRET_KEY` is sensitive — never log or expose.
- WebSocket `token` query parameter is visible in server logs — ensure logs redact JWT values in production.

## Validation Checklist
- [ ] WebSocket endpoint starts with valid config (no missing required variables).
- [ ] Missing env values fail fast with clear error messages.
- [ ] `WS_HEARTBEAT_INTERVAL` and `WS_STALE_TIMEOUT` are logged at startup (non-secret values).
- [ ] Backend can verify Supabase JWT with configured `JWT_SECRET_KEY`.
- [ ] `TIMEZONE` env var correctly formats event timestamps with offset.
- [ ] Mobile connects to correct `WS_BASE_URL` for the environment.
- [ ] Production uses `wss://` not `ws://`.
