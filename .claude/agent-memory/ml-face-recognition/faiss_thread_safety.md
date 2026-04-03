---
name: FAISS Thread Safety Pattern
description: FAISSManager uses threading.RLock (not Lock) because rebuild() calls add_batch() internally -- re-entrant locking required
type: project
---

FAISSManager is a global singleton accessed by multiple threads (API request handlers + APScheduler attendance scan).

**Pattern:** `threading.RLock` wrapping all public methods.

**Why RLock not Lock:** `rebuild()` calls `add_batch()` and `save()` internally. A regular `Lock` would deadlock on the nested acquisition. `RLock` allows the same thread to re-enter.

**Methods locked:**
- Mutating: `add()`, `add_batch()`, `remove()`, `rebuild()`, `save()`, `load_or_create_index()`
- Read: `search()`, `search_batch()`, `search_with_margin()`

**Note:** `search_with_margin()` delegates to `search()` but does NOT acquire the lock itself -- it relies on `search()` acquiring it. This is safe with RLock and avoids unnecessary nesting.

**Note:** `save()` releases the lock before firing async Redis notification to avoid holding the lock during I/O.

**How to apply:** Any new public method on FAISSManager that reads or mutates `self.index` or `self.user_map` must use `with self._lock:`.
