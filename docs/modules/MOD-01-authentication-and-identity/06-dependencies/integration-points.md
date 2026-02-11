# Integration Points

## Supabase Auth Integrations
- Backend creates users via Supabase Admin API on registration (`supabase.auth.admin.createUser()`)
- Backend verifies Supabase JWT on all protected routes (JWT secret from env)
- Mobile uses Supabase client SDK for login, refresh, password reset
- Supabase sends email verification and password reset emails automatically

## Backend Integrations
- User repository / database access layer (local `users` table)
- Supabase JWT verification middleware (FastAPI dependency)
- Request validation and exception handling middleware
- Rate limiting middleware (10 req/min on auth endpoints)

## Mobile Integrations
- Supabase client SDK (`@supabase/supabase-js`) for auth operations
- Auth screens state management (Zustand or Context)
- Supabase session persistence (via Supabase client storage adapter)
- API service layer for backend endpoints (`/auth/verify-student-id`, `/auth/register`, `/auth/me`)
- Deep link handling for password reset flow

## Data Integrations
- University identity source produced by import scripts (`MOD-11`)
- Faculty account pre-seeding workflow (Supabase Auth + local DB)
- Email confirmation sync: Supabase Auth → local `users.email_confirmed_at`

## Downstream Module Consumers
- `MOD-09` Student app session flow
- `MOD-10` Faculty app session flow
- Protected endpoints across all other backend modules (use JWT verification middleware)
