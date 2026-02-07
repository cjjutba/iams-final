# Data Model Inventory

## Primary Data Stores Used by MOD-03
1. `face_registrations` table
2. `users` table (identity linkage)
3. Local FAISS index file

## Entities
- Face registration metadata
- Embedding ID mapping
- Active/inactive registration state

## Ownership
- `face_registrations`: backend persistence layer
- FAISS index: ML/face service runtime storage
- `users`: auth identity linkage
