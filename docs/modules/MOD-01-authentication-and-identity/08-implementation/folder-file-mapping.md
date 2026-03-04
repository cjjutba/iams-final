# Folder and File Mapping

## Backend Expected Touchpoints
- `backend/app/routers/auth.py` — Auth router (verify-student-id, register, me endpoints)
- `backend/app/schemas/auth.py` — Pydantic schemas for auth request/response (including phone field)
- `backend/app/services/auth_service.py` — Auth business logic (Supabase Admin API integration)
- `backend/app/repositories/user_repository.py` — User DB access (including email_confirmed_at, phone)
- `backend/app/utils/security.py` — Supabase JWT verification, auth middleware
- `backend/app/utils/supabase_client.py` — Supabase Admin client initialization (service role key)

## Mobile Expected Touchpoints
- `mobile/src/lib/supabase.ts` — Supabase client initialization (`@supabase/supabase-js`)
- `mobile/src/screens/auth/StudentLoginScreen.tsx` — Login via Supabase client
- `mobile/src/screens/auth/FacultyLoginScreen.tsx` — Login via Supabase client (pre-seeded)
- `mobile/src/screens/auth/ForgotPasswordScreen.tsx` — Password reset request via Supabase
- `mobile/src/screens/auth/SetNewPasswordScreen.tsx` — Password reset completion via Supabase
- `mobile/src/screens/auth/RegisterStep1Screen.tsx` — Identity verification (backend API)
- `mobile/src/screens/auth/RegisterStep2Screen.tsx` — Account setup (email, phone, password)
- `mobile/src/screens/auth/RegisterReviewScreen.tsx` — Registration submit (backend API)
- `mobile/src/screens/auth/EmailVerificationPendingScreen.tsx` — Post-registration email check
- `mobile/src/services/authService.ts` — Backend API calls (verify-student-id, register, me)
- `mobile/src/store/authStore.ts` — Auth state management (Supabase session + user profile)

## Docs to Keep in Sync
- `docs/main/master-blueprint.md`
- `docs/main/api-reference.md`
- `docs/main/database-schema.md`
- `docs/main/technical-specification.md`
- `docs/main/implementation.md`
- `docs/modules/MOD-01-authentication-and-identity/`
