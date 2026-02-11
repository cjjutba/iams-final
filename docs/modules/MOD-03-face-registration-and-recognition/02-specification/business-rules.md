# Business Rules

## Auth Provider
- Supabase Auth is the authentication provider (established in MOD-01).
- Student-facing endpoints require Supabase JWT; edge-facing endpoints require shared API key.

## Registration Rules
1. Student face registration requires 3-5 valid images.
2. One active face registration per user.
3. Re-registration replaces or deactivates previous active embedding mapping.
4. Only authenticated students (valid Supabase JWT, `is_active = true`, `email_confirmed_at IS NOT NULL`) can register faces.

## Recognition Rules
1. Recognition uses configured threshold (default 0.6, from `RECOGNITION_THRESHOLD`).
2. If score is below threshold, result must be `matched=false`.
3. Recognition response must always follow documented payload shape.
4. Backend resizes incoming face crops to model input size (160x160) before inference.

## Persistence Rules
1. `face_registrations` and FAISS index must remain synchronized.
2. On remove/deactivate, FAISS mapping must be updated or rebuild strategy applied.
3. FAISS index file must be persisted after write operations.
4. On user deletion (triggered by MOD-02): delete `face_registrations` row, remove/exclude FAISS entry, persist index.

## Security Rules
1. Face embeddings are not reversible to original image.
2. Raw registration images should be minimized or handled per storage policy.
3. Student-facing endpoints (`POST /face/register`, `GET /face/status`) require Supabase JWT verification via middleware from MOD-01.
4. Edge-facing endpoint (`POST /face/recognize`) requires API key (`X-API-Key` header) validated against `EDGE_API_KEY`.
5. Invalid or missing auth credentials return `401`.
