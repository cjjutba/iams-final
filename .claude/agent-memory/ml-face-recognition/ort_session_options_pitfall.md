---
name: ORT get_session_options() Returns a Copy
description: onnxruntime InferenceSession.get_session_options() returns a COPY -- setting thread counts on it has no effect on the live session
type: project
---

`ort.InferenceSession.get_session_options()` returns a **copy** of the session options, not a reference.

Setting `opts.intra_op_num_threads` or `opts.inter_op_num_threads` on the returned object does nothing to the running session.

**Why:** This was dead code in `insightface_model.py` that appeared to configure thread counts post-hoc but had zero effect. Removed 2026-03-30.

**How to apply:** Control ORT thread counts via environment variables (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`) set BEFORE session creation, or via `SessionOptions` passed to the `InferenceSession` constructor. InsightFace creates sessions internally, so env vars are the only viable approach.
