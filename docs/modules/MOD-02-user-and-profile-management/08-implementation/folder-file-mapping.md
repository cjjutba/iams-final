# Folder and File Mapping

## Backend Expected Touchpoints
- `backend/app/routers/users.py` — CRUD endpoints for users
- `backend/app/schemas/user.py` — Pydantic schemas (include phone, email_confirmed; field rules for PATCH)
- `backend/app/services/user_service.py` — Business logic (field validation, delete orchestration)
- `backend/app/repositories/user_repository.py` — Database queries
- `backend/app/utils/dependencies.py` — Auth/role checks (Supabase JWT middleware from MOD-01)
- `backend/app/utils/supabase_client.py` — Supabase Admin API client (used for `deleteUser`)

## Mobile Expected Touchpoints
- `mobile/src/screens/student/StudentProfileScreen.tsx` — Display phone, email_confirmed
- `mobile/src/screens/student/StudentEditProfileScreen.tsx` — Editable: name, phone; email read-only
- `mobile/src/screens/faculty/FacultyProfileScreen.tsx` — Display phone, email_confirmed
- `mobile/src/screens/faculty/FacultyEditProfileScreen.tsx` — Editable: name, phone; email read-only
- `mobile/src/services/userService.ts` — API wrappers for `/users/*` with Supabase JWT
- `mobile/src/store/authStore.ts` — User profile state

## Docs to Keep in Sync
- `docs/main/api-reference.md`
- `docs/main/database-schema.md`
- `docs/modules/MOD-02-user-and-profile-management/`
