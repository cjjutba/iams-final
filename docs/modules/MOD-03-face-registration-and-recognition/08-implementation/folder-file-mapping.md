# Folder and File Mapping

## Backend Expected Touchpoints
- `backend/app/routers/face.py` — Registration, recognition, status endpoints
- `backend/app/schemas/face.py` — Pydantic schemas for face requests/responses
- `backend/app/services/face_service.py` — Validation, embedding generation, FAISS search, deletion cleanup
- `backend/app/repositories/face_repository.py` — Database queries for face_registrations
- `backend/app/services/tracking_service.py` — Integration context (uses recognition results)
- `backend/app/utils/dependencies.py` — Supabase JWT middleware (from MOD-01) + API key validation
- `backend/app/config.py` — FAISS_INDEX_PATH, RECOGNITION_THRESHOLD, EDGE_API_KEY, FACENET_MODEL_PATH

## Mobile Expected Touchpoints
- `mobile/src/screens/auth/RegisterStep3Screen.tsx` — Face registration during onboarding (Supabase JWT)
- `mobile/src/screens/student/StudentFaceReregisterScreen.tsx` — Re-registration flow (Supabase JWT)
- `mobile/src/screens/common/CameraScreen.tsx` — Camera capture utility
- `mobile/src/services/faceService.ts` — API wrappers for `/face/*` with Supabase JWT

## Docs to Keep in Sync
- `docs/main/architecture.md`
- `docs/main/api-reference.md`
- `docs/main/implementation.md`
- `docs/main/database-schema.md`
- `docs/modules/MOD-03-face-registration-and-recognition/`
