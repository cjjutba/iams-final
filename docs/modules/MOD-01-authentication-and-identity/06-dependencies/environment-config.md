# Environment Configuration

## Required Variables (Auth Context)
| Variable | Description | Required By |
|---|---|---|
| `SUPABASE_URL` | Supabase project URL | Backend (Admin API), Mobile (Supabase client) |
| `SUPABASE_ANON_KEY` | Supabase anonymous/public key | Mobile (Supabase client SDK) |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (admin access) | Backend only (for Admin API user creation) |
| `SUPABASE_JWT_SECRET` | Supabase JWT secret for verifying tokens | Backend only (JWT verification middleware) |
| `DATABASE_URL` | PostgreSQL connection string (Supabase pooler) | Backend (local users table access) |

## Supabase Project Settings
| Setting | Value | Location |
|---|---|---|
| Email confirmation | Enabled (required) | Supabase Dashboard → Auth → Email |
| Access token expiry | 3600 seconds (60 min) or 1800 seconds (30 min) | Supabase Dashboard → Auth → Settings |
| Password minimum length | 8 characters | Supabase Dashboard → Auth → Settings |
| Email templates | Customize confirmation and reset emails | Supabase Dashboard → Auth → Email Templates |
| Redirect URLs | App deep link URLs for email verification and password reset | Supabase Dashboard → Auth → URL Configuration |

## Configuration Rules
- Never hardcode secrets in source code.
- `SUPABASE_SERVICE_ROLE_KEY` must only be used on the backend (never exposed to mobile).
- Keep `.env.example` synchronized with runtime requirements.
- Production must use secure transport (`https`) and production-grade secrets.

## Validation Checklist
- App starts with complete env configuration.
- Missing env values fail fast with clear errors.
- Backend can verify Supabase JWT with configured secret.
- Backend can create Supabase Auth users with service role key.
- Supabase email templates are configured for confirmation and password reset.
