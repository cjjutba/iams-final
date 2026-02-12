# Environment Configuration

## Required Variables
| Variable | Required | Description | Example |
|---|---|---|---|
| DATABASE_URL | Yes | PostgreSQL connection string (Supabase pooler) | `postgresql://postgres.xxx:pass@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres` |
| SUPABASE_URL | Yes | Supabase project URL for JWT verification | `https://fspnxqmewtxmuyqqwwni.supabase.co` |
| SUPABASE_ANON_KEY | Yes | Supabase anon key for JWT verification | `eyJhbGci...` |
| JWT_SECRET_KEY | Yes | Secret key for JWT token operations | `your-secret-key-here` |
| TIMEZONE | No | Timezone for date/time interpretation (default: Asia/Manila) | `Asia/Manila` |

## Security Rules
- `JWT_SECRET_KEY` must never be committed to source control.
- `DATABASE_URL` credentials must be protected (use `.env` file, never hardcode).
- `.env` must be in `.gitignore`.
- All endpoints validate Supabase JWT before processing any request.

## Configuration Rules
- Time/date interpretation must be consistent across all attendance queries (use TIMEZONE env var).
- Missing auth/db config should fail fast at startup (application should not start with missing required variables).
- Attendance status constants (`present`, `late`, `absent`, `early_leave`) should be centrally defined.

## Validation Checklist
- [ ] Database connection works with DATABASE_URL.
- [ ] Supabase JWT verification works with SUPABASE_URL and SUPABASE_ANON_KEY.
- [ ] Attendance endpoints return data with valid Supabase JWT.
- [ ] Date range filters and "today" queries use consistent timezone (TIMEZONE env var).
- [ ] Role-based access is enforced (faculty-only endpoints reject student role with 403).
- [ ] Missing/invalid JWT returns 401 on all endpoints.
- [ ] Manual entry requires faculty/admin role and stores audit trail (remarks, updated_by, updated_at).
