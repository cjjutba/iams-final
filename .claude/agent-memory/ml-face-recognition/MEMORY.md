# ML Face Recognition Agent Memory

## Critical Learnings

### FastAPI UploadFile Constructor (2026-02-07)
**Issue:** Tests failed with `TypeError: UploadFile.__init__() got unexpected keyword argument 'content_type'`

**Root Cause:** FastAPI/Starlette's UploadFile constructor signature:
```python
UploadFile(file: BinaryIO, *, size: int | None, filename: str | None, headers: Headers | None)
```
- `file` is the first positional argument (required)
- `content_type` is NOT a valid parameter
- To set content-type, use `headers` parameter instead

**Correct Test Pattern:**
```python
from fastapi import UploadFile
import io

img_bytes = io.BytesIO(image_data)
upload_file = UploadFile(
    file=img_bytes,
    filename="test.jpg"
    # NO content_type parameter!
)
```

**Files Fixed:**
- `c:\.cjjutba\.thesis\iams\backend\tests\integration\test_registration_flow.py` (2 helper methods)

---

### Face Re-Registration Logic (2026-02-07)
**Issue:** `test_reregister_existing_face` failed with `UNIQUE constraint failed: face_registrations.user_id`

**Root Cause:**
- `face_registrations.user_id` has a UNIQUE constraint (line 38 of model)
- Original `reregister_face()` called `deactivate()` which set `is_active=False` but kept the record
- Calling `register_face()` tried to INSERT a new record → violated UNIQUE constraint

**Solution:** Changed `reregister_face()` to DELETE old registration instead of deactivating
```python
# OLD: deactivate (sets is_active=False)
self.face_repo.deactivate(user_id)

# NEW: delete (removes record entirely)
old_registration = self.face_repo.get_by_user(user_id)
if old_registration:
    self.face_repo.delete(str(old_registration.id))
```

**Rationale:**
- Old FAISS embedding is already invalidated when re-registering
- No need to keep inactive records (adds clutter)
- Respects UNIQUE constraint on user_id
- Cleaner data model

**Files Modified:**
- `c:\.cjjutba\.thesis\iams\backend\app\services\face_service.py` (lines 244-254)

---

## Test Results
- **Before:** 6 face registration tests failing
- **After:** All 12 tests in `test_registration_flow.py` passing
- **Full Suite:** 275 passing (9 pre-existing failures unrelated to face recognition)

---

## Design Notes

### FAISS Index Management
- **Index Type:** `IndexFlatIP` (inner product, no native delete support)
- **On User Removal:** Must rebuild index or filter results at search time
- **Embedding Storage:** 512-dim vectors stored as bytes in `face_registrations.embedding_vector` for index rebuilding

### Face Registration Constraints
- **Images Required:** 3-5 per user
- **Embedding Dimension:** 512 (L2-normalized unit vectors)
- **Unique Constraint:** One active registration per user (enforced at DB level via `user_id` UNIQUE)

### Current Limitations
- `face_registrations.user_id` UNIQUE constraint prevents soft-delete pattern
- Consider future enhancement: change to UNIQUE constraint on `(user_id, is_active)` if audit trail needed
