# ML Face Recognition Agent Memory

## Index

- [faiss_thread_safety.md](faiss_thread_safety.md) -- FAISSManager RLock pattern and re-entrancy rationale
- [ort_session_options_pitfall.md](ort_session_options_pitfall.md) -- ORT get_session_options() returns a copy (dead code trap)

## Critical Learnings

### FastAPI UploadFile Constructor (2026-02-07)
- `content_type` is NOT a valid UploadFile parameter; use `headers` instead

### Face Re-Registration Logic (2026-02-07)
- `face_registrations.user_id` has UNIQUE constraint -- must DELETE (not deactivate) before re-INSERT

### FAISS Reregister ID Sync (2026-03-30)
- `reregister_face()` must rebuild FAISS BEFORE calling `register_face()`, not after
- Reason: `register_face` assigns IDs via `index.ntotal`; a post-register rebuild reassigns all IDs from scratch, desynchronizing DB `faiss_id` values

### FAISS remove() Limitation (2026-03-30)
- `faiss.remove(fid)` only deletes from `user_map`, NOT from `IndexFlatIP` (no native delete)
- After rollback, orphaned vectors remain -- must call `rebuild_faiss_index()` to purge

## Design Notes

### FAISS Index Management
- **Index Type:** `IndexFlatIP` (inner product, no native delete)
- **Thread Safety:** `threading.RLock` on all read/write methods (added 2026-03-30)
- **RLock rationale:** `rebuild()` calls `add_batch()` internally -- needs re-entrant lock
- **Embedding Storage:** 512-dim vectors as bytes in `face_embeddings.embedding_vector`
- **rebuild()** now returns `dict[int, str]` mapping for DB faiss_id sync

### Face Registration Constraints
- **Images Required:** 3-5 per user
- **Embedding Dimension:** 512 (L2-normalized unit vectors)
- **Zero-norm guard:** `norm < 1e-6` check before division (added 2026-03-30)
- **Unique Constraint:** One active registration per user (`user_id` UNIQUE)

## Test Environment Notes
- FAISS Manager tests: all 27 pass (test_faiss_manager.py)
- Face service tests: pre-existing SQLAlchemy backref conflict on `EarlyLeaveEvent` blocks DB fixture setup
- Auth/security tests: `jwt` module missing from test venv
