# Implementation Plan (MOD-03)

## Phase 1: Foundations
- Verify Supabase JWT middleware from MOD-01 is working for student-facing endpoints.
- Implement API key validation middleware for edge-facing endpoint (`EDGE_API_KEY`).
- Configure FaceNet model path (`FACENET_MODEL_PATH`) and FAISS index path (`FAISS_INDEX_PATH`).
- Build validation utilities for registration image constraints.
- Verify `face_registrations` table has all required columns (id, user_id, embedding_id, registered_at, is_active).

## Phase 2: Registration Pipeline
- Implement `FUN-03-01` input validation (3-5 images, face detection, quality checks; Supabase JWT required).
- Implement `FUN-03-02` embedding generation (resize to 160x160, FaceNet inference, 512-d output, average aggregation).
- Implement `FUN-03-03` persistence and index sync (face_registrations + FAISS; re-registration lifecycle).

## Phase 3: Recognition and Status
- Implement `FUN-03-04` recognition endpoint (API key auth, resize to 160x160, FAISS search, threshold logic).
- Implement `FUN-03-05` registration status endpoint (Supabase JWT auth).

## Phase 4: Cross-Module Coordination
- Implement face data cleanup service method (`delete_face_data_for_user(user_id)`) for MOD-02 deletion.
- Wire registration/re-registration screens with Supabase JWT in Authorization header.
- Validate recognition behavior against edge caller context with API key.

## Phase 5: Validation
- Run unit/integration/E2E tests (including auth scenarios: JWT, API key, expired, missing).
- Validate acceptance criteria and update traceability.
- Verify MOD-02 deletion correctly triggers face data cleanup.
