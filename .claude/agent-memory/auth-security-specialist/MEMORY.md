# Auth Security Specialist - Memory

## Project Auth Architecture
- **Auth pattern**: Custom JWT for all users (students + faculty), NOT Supabase Auth for students yet
- **Password hashing**: bcrypt via `passlib.context.CryptContext` in `backend/app/utils/security.py`
- **JWT**: HS256, access + refresh tokens via `create_access_token` / `create_refresh_token` in security.py
- **Token refresh**: `verify_token()` checks `type: "refresh"` claim, generates new access token only
- **RBAC roles**: student, faculty, admin (enum in `app/models/user.py::UserRole`)
- **Pydantic version**: v2 (2.12.5) - use `model_dump()` not `dict()`

## Key Files
- `backend/app/services/auth_service.py` - AuthService class (verify_student_id, register_student, login, refresh, change_password)
- `backend/app/schemas/auth.py` - Auth request/response Pydantic models
- `backend/app/routers/auth.py` - FastAPI router for auth endpoints
- `backend/app/utils/security.py` - hash_password, verify_password, create_access_token, create_refresh_token, validate_password_strength, verify_token
- `backend/app/utils/dependencies.py` - get_current_user dependency
- `backend/app/utils/exceptions.py` - AuthenticationError, ValidationError, NotFoundError
- `backend/app/repositories/user_repository.py` - UserRepository (create, get_by_id, get_by_identifier, update)

## Registration Flow (2-step + face)
1. POST `/api/v1/auth/verify-student-id` - Validates student ID + birthdate against student_records
2. POST `/api/v1/auth/register` - Creates account with student_id, email, password, first_name, last_name
3. POST `/api/v1/face/register` - Face registration (separate endpoint)

## Security Audit (2026-03-30)
- [security_audit_2026_03_30.md](security_audit_2026_03_30.md) - Full audit: 5 Critical, 8 High, 10 Medium, 6 Low findings
- Top priorities: WebSocket auth, Edge API auth, rate limiting on login/register/refresh, refresh token rotation, CORS lockdown
- RefreshToken DB model exists but is UNUSED - refresh only checks JWT signature
- Logout is a client-side no-op (stateless JWT, no server revocation)
- EDGE_API_KEY config exists but is never enforced
- Faculty can update any user / deregister any face (privilege escalation)

## Security Notes
- Login error messages are generic ("Invalid email/student ID or password") - no user enumeration
- No auth tests exist yet (`backend/tests/test_auth*.py` missing)
- Faculty accounts are pre-seeded only (no self-registration in MVP)
- `from_attributes = True` used on UserResponse Config (Pydantic v2 style)

## JRMSU Student ID Format
- Example: `21-A-02177` (XX-X-XXXXX pattern)
- MVP does not enforce strict format validation - accepts any string >= 3 chars
