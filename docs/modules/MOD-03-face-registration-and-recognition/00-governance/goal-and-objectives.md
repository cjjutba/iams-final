# Goal and Objectives

## Module Goal
Provide reliable face registration and recognition for students, with consistent embedding storage and FAISS index synchronization. All student-facing endpoints are protected by Supabase JWT middleware (from MOD-01); edge-facing recognition uses shared API key authentication.

## Primary Objectives
1. Validate and accept 3-5 registration images per student.
2. Generate stable 512-d face embeddings (FaceNet, 160x160 input).
3. Persist and synchronize embeddings between DB and FAISS index.
4. Recognize incoming face crops with configurable threshold (backend handles resize from edge crop size to model input size).
5. Expose registration status for app flows (Supabase JWT protected).
6. Coordinate with MOD-02 for face data cleanup on user deletion.

## Success Outcomes
- Invalid registration inputs are rejected with clear errors.
- Embeddings are stored safely and mapped to users correctly.
- Recognition returns deterministic matched/unmatched response shape.
- DB and FAISS remain synchronized through add/update/remove lifecycle.
- Protected endpoints enforce Supabase JWT; edge endpoints enforce API key.

## Non-Goals (for MOD-03 MVP)
- Multi-modal biometrics.
- Custom model training pipeline.
- Cross-device distributed vector databases.
- Rate limiting on face endpoints.

## Stakeholders
- Students: complete face registration/re-registration.
- Faculty: indirectly rely on recognition for attendance.
- Backend/ML implementers: maintain recognition pipeline quality.
- Operations: maintain FAISS persistence and integrity.