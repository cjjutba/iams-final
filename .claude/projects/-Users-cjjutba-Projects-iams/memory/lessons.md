# Lessons

## 2026-04-03: Admin portal API integration findings
- The admin portal uses FastAPI backend for all data — NOT Supabase directly (except email-confirmed.tsx for mobile user redirect links)
- Backend error format: `{"success": false, "error": {"code": "AuthenticationError", "message": "..."}}` — admin portal extracts `error.response?.data?.error?.message`
- Admin calls `/analytics/at-risk` but backend has `/analytics/at-risk-students` — path mismatch causes 404
- Admin calls `/analytics/class/{id}` but backend has `/analytics/class/{id}/overview` — path mismatch
- Password `"123"` doesn't meet `validate_password_strength()` rules (>=8 chars) but that validation is only on API endpoints, not seed scripts which call `hash_password()` directly — login just uses `verify_password()` which is hash-only
- The Vite dev server proxy in `vite.config.ts` routes `/api/*` → `http://localhost:8000`, so no CORS issues in dev
- The audit_logs migration already exists (`c3d4e5f6a7b8`) with columns: id, admin_id, action, target_type, target_id, details, created_at — model must match
