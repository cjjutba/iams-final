# MVP Scope

## In Scope
- Face registration upload and validation (3-5 images).
- Embedding generation and storage (FaceNet 512-d, 160x160 input).
- Recognition endpoint for incoming face crops (backend resizes to model input size).
- Registration status endpoint (Supabase JWT protected).
- FAISS/DB synchronization lifecycle documentation.
- API key authentication for edge-facing recognition endpoint.
- Coordination with MOD-02 for face data cleanup on user deletion.

## Out of Scope
- Custom model training.
- Liveness detection beyond baseline validation checks.
- Large-scale multi-index sharding.
- Rate limiting on face endpoints.

## MVP Constraints
- Recognition model: FaceNet (InceptionResnetV1).
- Embedding size: 512 dimensions.
- Model input: 160x160 RGB (backend resizes incoming crops).
- Match threshold default: 0.6 (configurable via `RECOGNITION_THRESHOLD`).
- One active face registration per user.
- No local password storage — Supabase Auth manages credentials (from MOD-01).
- Student-facing endpoints require Supabase JWT; edge-facing endpoints require API key.

## MVP Gate Criteria
- `FUN-03-01` through `FUN-03-05` implemented and tested.
- Invalid image inputs are blocked.
- Recognition matched/unmatched behavior works as documented.
- FAISS and `face_registrations` synchronization is validated.
- Supabase JWT enforced on `POST /face/register` and `GET /face/status`.
- API key enforced on `POST /face/recognize`.
- User deletion (MOD-02) correctly cleans up face_registrations and FAISS.