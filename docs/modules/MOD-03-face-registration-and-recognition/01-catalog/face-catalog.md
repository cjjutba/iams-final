# Face Registration and Recognition Module Catalog

## Auth Context
- Student-facing endpoints protected by Supabase JWT middleware (from MOD-01).
- Edge-facing recognition endpoint protected by shared API key (`X-API-Key` header).

## Subdomains
1. Face Registration Input Validation
- Validate registration image count and quality constraints.

2. Embedding Generation
- Convert accepted face images to 512-d vectors (FaceNet, 160x160 input; backend resizes incoming crops).

3. Embedding Persistence and Index Sync
- Save face mapping to DB and vectors to FAISS.

4. Face Recognition
- Match incoming crop against indexed embeddings.

5. Registration Status
- Return whether user has active registration.

## Function Catalog
| Function ID | Name | Summary |
|---|---|---|
| FUN-03-01 | Upload and Validate Face Images | Validate 3-5 registration images (Supabase JWT required) |
| FUN-03-02 | Generate Embeddings | Produce 512-d embedding vectors from face inputs (160x160 resize) |
| FUN-03-03 | Store and Sync Embeddings | Persist DB mapping and FAISS index entries; handle MOD-02 deletion |
| FUN-03-04 | Recognize Face | Match incoming face with configurable threshold (API key auth) |
| FUN-03-05 | Check Registration Status | Return face registration state for user (Supabase JWT required) |

## Actors
- Student
- Backend/ML service
- Edge ingestion caller (RPi)
- Mobile app
- Supabase Auth (identity provider from MOD-01)

## Interfaces
- REST face endpoints (`/face/*`)
- Supabase JWT middleware (for register, status)
- API key validation (for recognize)
- FAISS index file access
- `face_registrations` table
- Supabase Admin API (via MOD-02 for user deletion cleanup)
