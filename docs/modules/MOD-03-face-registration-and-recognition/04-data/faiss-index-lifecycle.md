# FAISS Index Lifecycle

## Baseline
- Index type: `IndexFlatIP`
- Dimensions: `512`
- Model input: `160x160` RGB (backend resizes incoming crops to this size)
- Search: top-1 nearest neighbor
- Threshold: configurable via `RECOGNITION_THRESHOLD` (default 0.6)

## Lifecycle Operations
1. Add (Registration)
- Resize images to 160x160 and generate embedding via FaceNet
- Add vector to FAISS
- Write `face_registrations` row
- Persist index to disk

2. Update (Re-registration)
- Deactivate/remove previous mapping
- Remove or exclude old vector
- Add new vector and persist index

3. Remove (User Deletion — triggered by MOD-02)
- Delete `face_registrations` row
- Remove/exclude vector in FAISS
- Persist index
- Note: `IndexFlatIP` does not support native delete — rebuild index excluding removed ID, or filter at search time

4. Rebuild
- Export active embeddings from DB
- Rebuild FAISS index from scratch
- Save rebuilt file
- Prefer doing this during low traffic

## Consistency Rule
`face_registrations` and FAISS must always represent the same active set.

## Cross-Module Coordination
- **MOD-02 (User Deletion):** When a user is deleted, MOD-02 calls MOD-03's face cleanup service to remove face_registrations and FAISS entry. This is step 1-2 of MOD-02's 5-step deletion process (before Supabase Auth cleanup).
- **MOD-04 (Edge Processing):** `POST /face/process` (owned by MOD-04) feeds recognition results through FAISS. Changes to batch payload must be reflected here.
