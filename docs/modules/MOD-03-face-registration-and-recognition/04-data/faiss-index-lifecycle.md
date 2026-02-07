# FAISS Index Lifecycle

## Baseline
- Index type: `IndexFlatIP`
- Dimensions: `512`
- Search: top-1 nearest neighbor

## Lifecycle Operations
1. Add
- Generate embedding
- Add vector to FAISS
- Write `face_registrations` row
- Persist index to disk

2. Update (re-registration)
- Deactivate/remove previous mapping
- Remove or exclude old vector
- Add new vector and persist index

3. Remove
- Deactivate/delete registration mapping
- Remove/exclude vector in FAISS
- Persist index

4. Rebuild
- Export active embeddings
- Rebuild FAISS index
- Save rebuilt file

## Consistency Rule
`face_registrations` and FAISS must always represent the same active set.
