# Glossary

- **Access Token:** Short-lived Supabase-issued JWT used on protected API requests.
- **Refresh Token:** Longer-lived Supabase-managed token used to request a new access token.
- **Supabase Auth:** The authentication provider used by IAMS; handles user credentials, email verification, and password reset.
- **Supabase Client SDK:** JavaScript library (`@supabase/supabase-js`) used by the mobile app to interact with Supabase Auth for login, refresh, and password reset.
- **Supabase Admin API:** Server-side Supabase API used by the backend to create users during registration (`supabase.auth.admin.createUser()`).
- **Identity Verification:** Pre-registration check that student ID exists in university dataset.
- **Pre-seeded Faculty:** Faculty account created ahead of time by import/seed process; faculty cannot self-register in MVP.
- **Protected Route:** Backend endpoint requiring `Authorization: Bearer <supabase_jwt>`.
- **JWT:** JSON Web Token used for stateless auth claims; issued by Supabase Auth.
- **Auth Context:** Current authenticated user identity and role resolved from Supabase JWT + local `users` table.
- **Email Verification:** Process where Supabase sends a confirmation email on registration; user must click link to verify; backend enforces `email_confirmed_at`.
- **Password Reset:** Process where Supabase sends a reset email; user clicks link and sets new password via Supabase client.
- **JWT Secret:** Supabase project's JWT secret key used by backend to verify JWT signatures (`SUPABASE_JWT_SECRET` env var).
