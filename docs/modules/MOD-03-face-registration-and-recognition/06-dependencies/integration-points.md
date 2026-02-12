# Integration Points

## Backend Integrations
- Face service for validation, embedding generation, and FAISS search.
- Repository for `face_registrations` persistence.
- Config layer for threshold/model/index path settings.
- Supabase JWT middleware (from MOD-01) for student-facing endpoint protection.
- API key validation middleware for edge-facing endpoint protection.

## Mobile Integrations
- Student registration step-3 and re-registration screens.
- Camera utility screen and file upload handling.
- Supabase JWT passed in `Authorization` header for all face API calls.

## Cross-Module Integrations
- `MOD-01`: Supabase JWT middleware for auth; user identity context.
- `MOD-02`: User deletion triggers face data cleanup (face_registrations + FAISS). MOD-03 exposes `delete_face_data_for_user(user_id)` service method.
- `MOD-04`: Edge process payload flow (`POST /face/process`); shared API key auth pattern.
- `MOD-06`: Attendance actions driven by recognition results.
- `MOD-07`: Presence tracking uses recognition detections.

## Auth Integration Details
- **Supabase JWT (MOD-01):** Reuse `backend/app/utils/dependencies.py` middleware. No custom JWT implementation in MOD-03.
- **API Key (Edge):** Validate `X-API-Key` header against `EDGE_API_KEY` env variable. Shared validation logic can be used by both MOD-03 (`/face/recognize`) and MOD-04 (`/face/process`).
