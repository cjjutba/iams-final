# Environment Configuration

## Required Variables (Presence Context)
| Variable | Description | Default | Required By |
|---|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string (Supabase pooler, IPv4) | — | Backend (presence queries) |
| `SUPABASE_URL` | Supabase project URL | — | Backend (auth verification) |
| `SUPABASE_ANON_KEY` | Supabase anonymous/public key | — | Mobile (Supabase client SDK) |
| `JWT_SECRET_KEY` | Supabase JWT secret for token verification | — | Backend (JWT verification middleware) |
| `SCAN_INTERVAL` | Scan interval in seconds | `60` | Backend (presence service scan loop) |
| `EARLY_LEAVE_THRESHOLD` | Consecutive miss count before flagging | `3` | Backend (early-leave detection) |
| `TIMEZONE` | System timezone for session boundaries | `Asia/Manila` | Backend (session date/time, "today" queries) |

## Configuration Rules
- Threshold and interval must be configurable per deployment (env vars, no code changes).
- Invalid threshold config (e.g., non-integer, negative) should fail fast at startup.
- Session timing assumptions should be explicit using `TIMEZONE` env var.
- `SCAN_INTERVAL` and `EARLY_LEAVE_THRESHOLD` are logged at startup (non-secret).

## Security Rules
- Never hardcode secrets in source code.
- Keep `.env.example` synchronized with runtime requirements.
- Production must use secure transport (`https`) and production-grade secrets.
- `JWT_SECRET_KEY` is sensitive — never log or expose.

## Validation Checklist
- [ ] Presence service starts with valid config (no missing required variables).
- [ ] Missing env values fail fast with clear error messages.
- [ ] `SCAN_INTERVAL` and `EARLY_LEAVE_THRESHOLD` are logged at startup (non-secret values).
- [ ] Backend can verify Supabase JWT with configured `JWT_SECRET_KEY`.
- [ ] `TIMEZONE` env var correctly interprets "today" queries and session boundaries.
- [ ] Early-leave behavior reflects configured threshold values.
- [ ] Database connection uses Supabase pooler (IPv4) not direct connection (IPv6 only).
