# Data Model Inventory

## Primary Data Stores Used by MOD-03
1. `face_registrations` table
2. `users` table (identity linkage)
3. Local FAISS index file
4. Supabase Auth user records (identity context from MOD-01)

## Entities
- Face registration metadata (embedding_id, registered_at, is_active)
- Embedding ID mapping (links user to FAISS vector)
- Active/inactive registration state

## Ownership
- `face_registrations`: backend persistence layer
- FAISS index: ML/face service runtime storage
- `users`: auth identity linkage (owned by MOD-01/MOD-02)
- Supabase Auth: identity provider (from MOD-01)

## Cross-Module Data Coordination

### MOD-02 User Deletion
When MOD-02 deletes a user (hard delete), it triggers cleanup in MOD-03:
1. Delete `face_registrations` row for the user.
2. Remove or exclude the embedding from FAISS index.
3. Rebuild FAISS index if using `IndexFlatIP` (no native delete support).
4. Persist FAISS index to disk.

MOD-03 exposes a service method (e.g., `delete_face_data_for_user(user_id)`) that MOD-02's delete orchestration calls.
