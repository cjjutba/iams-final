# Environment Configuration

## Required Variables (Schedule Context)
| Variable | Required | Description | Example |
|---|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string (Supabase pooler) | `postgresql://user:pass@host:6543/postgres` |
| `SUPABASE_URL` | Yes | Supabase project URL | `https://fspnxqmewtxmuyqqwwni.supabase.co` |
| `SUPABASE_ANON_KEY` | Yes | Supabase anonymous key for JWT verification | `eyJ...` |
| `JWT_SECRET_KEY` | Yes | JWT secret for token verification | `your-secret-key` |
| `TIMEZONE` | No | Server timezone for time comparisons (default: Asia/Manila) | `Asia/Manila` |

## Configuration Rules
- `TIMEZONE` must be a valid IANA timezone name. Default: `Asia/Manila` (+08:00) for JRMSU pilot.
- All schedule `start_time`/`end_time` comparisons use configured timezone.
- Missing auth/db config should fail fast at startup.
- Query behavior must be deterministic across environments (same timezone, same sort order).

## Security Rules
- `JWT_SECRET_KEY` must never be committed to source control.
- `DATABASE_URL` credentials must be protected.
- All endpoints validate Supabase JWT before processing.

## Validation Checklist
- [ ] Database connection works with `DATABASE_URL`.
- [ ] Supabase JWT verification works with `SUPABASE_URL` and `SUPABASE_ANON_KEY`.
- [ ] Schedule endpoints return data with valid Supabase JWT.
- [ ] Day/time filters behave consistently (deterministic sort order).
- [ ] Role-based schedule access checks are enabled (admin-only for POST, role-scoped for GET /me).
- [ ] Timezone is configured and time comparisons are consistent.
- [ ] Missing/invalid JWT returns 401 on all endpoints.
