# Face Registration and Recognition Module Catalog

## Subdomains
1. Face Registration Input Validation
- Validate registration image count and quality constraints.

2. Embedding Generation
- Convert accepted face images to 512-d vectors.

3. Embedding Persistence and Index Sync
- Save face mapping to DB and vectors to FAISS.

4. Face Recognition
- Match incoming crop against indexed embeddings.

5. Registration Status
- Return whether user has active registration.

## Function Catalog
| Function ID | Name | Summary |
|---|---|---|
| FUN-03-01 | Upload and Validate Face Images | Validate 3-5 registration images |
| FUN-03-02 | Generate Embeddings | Produce embedding vectors from face inputs |
| FUN-03-03 | Store and Sync Embeddings | Persist DB mapping and FAISS index entries |
| FUN-03-04 | Recognize Face | Match incoming face with configurable threshold |
| FUN-03-05 | Check Registration Status | Return face registration state for user |

## Actors
- Student
- Backend/ML service
- Edge ingestion caller
- Mobile app

## Interfaces
- REST face endpoints (`/face/*`)
- FAISS index file access
- `face_registrations` table
