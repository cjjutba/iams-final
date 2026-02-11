# Environment Configuration

## Required Variables (User/Profile Context)
| Variable | Purpose | Used In |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection for user queries | All endpoints |
| `SUPABASE_URL` | Supabase project URL | Delete (Admin API) |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Admin API access | Delete user from Supabase Auth |
| `SUPABASE_JWT_SECRET` | JWT signature verification | Auth middleware on all endpoints |

## Configuration Rules
- Never hardcode secrets in source code.
- Keep `.env.example` synchronized with runtime requirements.
- Protected user endpoints must fail closed on missing auth config.
- `SUPABASE_SERVICE_ROLE_KEY` is required for delete operations (FUN-02-04).

## Validation Checklist
- User endpoints start successfully with complete config.
- Authorization checks are active in non-local environments.
- Profile update validation behaves consistently across environments.
- Delete operation can reach Supabase Admin API.
