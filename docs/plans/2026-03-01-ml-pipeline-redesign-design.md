# ML Pipeline Redesign — Design Document

**Date:** 2026-03-01
**Status:** Approved
**Approach:** Pipeline Redesign (Approach B) — one cohesive pass

## Problem Statement

The IAMS face detection/recognition/tracking pipeline has critical bugs, accuracy gaps, and streaming performance issues that prevent production readiness:

1. **Image size mismatch** — Edge sends 112x112 JPEG@70%, backend expects 160x160 for FaceNet
2. **No face alignment** — Raw crops go straight to FaceNet, costing 5-10% accuracy
3. **FAISS/DB sync risk** — No transaction safety between FAISS index and database
4. **Thread safety** — `PresenceService._active_sessions` has no locks
5. **Dual presence logging** — Two paths (Edge API + APScheduler) can double-count
6. **Slow streaming** — Recognition at 1.5fps, target is 30-60fps smooth video
7. **Documentation contradictions** — Batch policy, image sizes, HTTP codes differ across 4+ docs

## Target State

- Face recognition accuracy >= 92% (PRD requirement)
- Live feed at 30fps with real-time detection overlays
- Face registration works seamlessly end-to-end
- All concurrency/sync bugs fixed
- Single source of truth documentation

---

## Section 1: Preprocessing Pipeline

### Current State
- Edge: 112x112 crop, JPEG 70% quality
- Backend: Accepts any size, resizes to 160x160 (upscaling lossy compressed image)

### Proposed Changes

| Component | Current | Proposed |
|-----------|---------|----------|
| Edge crop size | 112x112 | **160x160** |
| Edge JPEG quality | 70% | **85%** |
| Backend validation | Accepts anything | **Reject < 160x160** |
| Mobile registration | Raw camera images | **Validate >= 160x160** |
| Normalization | `(pixel - 127.5) / 128.0` | Same (correct) |
| Color space | BGR -> RGB | Same (correct) |

### Files to Change
- `edge/app/config.py` — `FACE_CROP_SIZE` default 112 -> 160, `JPEG_QUALITY` 70 -> 85
- `edge/app/processor.py` — Update resize target
- `backend/app/services/ml/face_recognition.py` — Add minimum size validation
- `mobile/src/components/face/FaceScanCamera.tsx` — Ensure 160x160 minimum

---

## Section 2: Face Alignment (MTCNN)

### Current State
No face alignment. Raw crops go directly to FaceNet.

### Proposed Changes
Add MTCNN-based face alignment before embedding generation.

**Pipeline change:**
```
BEFORE: crop -> resize 160x160 -> normalize -> FaceNet
AFTER:  crop -> MTCNN detect landmarks -> affine align -> resize 160x160 -> normalize -> FaceNet
```

**Details:**
- MTCNN detects 5 facial landmarks (eyes, nose, mouth corners)
- Affine transform aligns face to standard template
- Runs on **backend only** (too heavy for RPi)
- Applied in `FaceNetModel.generate_embedding()` before preprocessing
- Both registration AND recognition use the same alignment
- Fallback: If MTCNN can't detect landmarks, skip alignment, use raw crop, log warning
- No new dependencies — MTCNN comes with `facenet-pytorch`

**Migration:** All registered faces need re-embedding after this change. Add migration step to re-process stored face images through the new pipeline and rebuild FAISS.

### Files to Change
- `backend/app/services/ml/face_recognition.py` — Add MTCNN alignment step

---

## Section 3: FAISS & Data Integrity

### Current State
No transaction wrapping. FAISS add and DB insert are independent operations. No reconciliation.

### Proposed Changes

**A. Registration Transaction Safety:**
```
1. Generate embedding
2. BEGIN DB transaction
3. INSERT face_registrations row
4. Add to FAISS index (in-memory)
5. COMMIT DB transaction
6. Save FAISS to disk
7. On ANY failure: ROLLBACK DB + revert FAISS in-memory state
```

**B. Startup Reconciliation:**
- Compare `FAISS.ntotal` vs `SELECT COUNT(*) FROM face_registrations WHERE is_active = true`
- If mismatch: trigger automatic FAISS rebuild from DB embeddings
- Log warning with details

**C. Periodic Health Check:**
- Lightweight reconciliation check every 30 minutes (APScheduler)
- Compare counts, flag anomalies
- Don't auto-rebuild — just alert

### Files to Change
- `backend/app/services/face_service.py` — Transaction wrapping with FAISS rollback
- `backend/app/main.py` — Startup reconciliation + periodic health job

---

## Section 4: Concurrency & Session Fixes

### Current State
- `_active_sessions` shared dict with no locks
- Edge API calls `log_detection()` directly AND APScheduler calls `run_scan_cycle()`
- Two writers to attendance tables = double-counting risk

### Proposed Changes

**A. Thread Safety:**
- Add `asyncio.Lock()` to `PresenceService`
- Wrap `log_detection()`, `start_session()`, `end_session()` with lock

**B. Unified Presence Logging (Single Writer):**
```
BEFORE (two paths):
  Path 1: Edge API -> log_detection() -> update attendance
  Path 2: APScheduler -> run_scan_cycle() -> check tracking -> update attendance

AFTER (single path):
  Edge API -> face recognized -> tracking_service.update() (stores detection only)
  APScheduler -> run_scan_cycle() -> reads tracking state -> update attendance (sole writer)
```

Edge API no longer directly updates attendance. It feeds the tracking service. The 60-second scan cycle is the sole writer. Edge API still returns matched users immediately for RPi feedback.

### Files to Change
- `backend/app/services/presence_service.py` — Add lock, refactor log_detection
- `backend/app/routers/face.py` — Remove direct log_detection, feed tracking service

---

## Section 5: Streaming Architecture (30-60fps)

### Current State
- Recognition at 1.5fps
- HLS streaming exists but not tuned
- No smooth overlay transitions

### Proposed Architecture

```
IP Camera --RTSP 30fps--> FFmpeg (HLS) --segments--> HLS Endpoint --> Mobile HLS Player (30fps)
IP Camera --RTSP 5-10fps--> Detection Thread --> RecognitionState --> WebSocket --> Mobile Overlay
```

Video display and detection are independent. Video streams at 30fps, detection runs at 5-10fps, overlays interpolate.

### Key Parameters

| Setting | Value | Rationale |
|---------|-------|-----------|
| HLS FPS | 30 | Smooth video |
| HLS segment duration | 2s | Balance latency vs buffering |
| HLS playlist size | 3 segments | ~6s buffer |
| Detection FPS | 5-10 | Recognition budget ~100-200ms/frame |
| WebSocket push rate | 5-10Hz | Match detection rate |
| Overlay fade duration | 200ms | Smooth transitions |

### Files to Change
- `backend/app/services/hls_service.py` — FFmpeg params (30fps, 720p, keyframe interval)
- `backend/app/services/recognition_service.py` — `RECOGNITION_FPS` 1.5 -> 5-10
- `backend/app/routers/live_stream.py` — WebSocket push rate
- `mobile/src/components/video/DetectionOverlay.tsx` — Animated transitions

---

## Section 6: Recognition Accuracy Tuning

### Expected Improvement

| Improvement | Expected Gain |
|-------------|---------------|
| 160x160 crops (from 112x112) | +2-3% |
| JPEG 85% (from 70%) | +1-2% |
| MTCNN face alignment | +5-8% |
| Top-3 search with margin check | +1-2% |
| **Combined** | **+9-15%** (target: 92%+) |

### Top-K Search with Confidence Margin
```
Search k=3, threshold 0.55
- If top match > 0.55 AND (top - second) > 0.1 -> confident match
- If top match > 0.55 AND (top - second) <= 0.1 -> ambiguous, use top, log warning
- If top match < 0.55 -> no match
```

Threshold lowered from 0.6 to 0.55 because alignment makes embeddings more consistent.

### Batch Processing Optimization
- `recognize_batch()` uses sequential recognition currently
- Change to `generate_embeddings_batch()` + `search_batch()` (single forward pass)
- Reduces per-face overhead from ~200ms to ~50ms at scale

### Quality Gate on Edge
- Raise detection confidence from 0.5 to 0.6
- Reject crops where detected face < 80x80 pixels in original frame

### Files to Change
- `backend/app/services/ml/face_recognition.py` — MTCNN alignment
- `backend/app/services/ml/faiss_manager.py` — Confidence margin in search
- `backend/app/services/face_service.py` — Batch recognition
- `backend/app/config.py` — New threshold params
- `edge/app/detector.py` — Raise confidence, min face size filter

---

## Section 7: Documentation Reconciliation

### New Document
`docs/main/ml-pipeline-spec.md` — single authoritative ML pipeline specification

### Contents
1. Preprocessing chain (camera to embedding, both edge and backend)
2. Face registration contract (images, count, alignment, averaging)
3. Face recognition contract (threshold, top-k, margin, batch)
4. Edge API contract (resolves batch conflict: **1-10, optimal 3-5**)
5. HTTP status codes (standardize on 422 for validation)
6. FAISS lifecycle (add, search, delete/rebuild, persistence, reconciliation)
7. Streaming spec (HLS params, overlay protocol, WebSocket format)
8. Threshold reference (all configurable thresholds with defaults and ranges)

### Existing Doc Updates
- `implementation.md` — Remove batch policy contradiction, reference ml-pipeline-spec
- `technical-specification.md` — Align HTTP codes and image requirements
- `edge-device-integration-guide.md` — Reference ml-pipeline-spec for API contract

---

## Summary of All Files to Change

### Backend
| File | Changes |
|------|---------|
| `app/services/ml/face_recognition.py` | MTCNN alignment, min size validation |
| `app/services/ml/faiss_manager.py` | Confidence margin search, top-k logic |
| `app/services/face_service.py` | Transaction safety, batch recognition, FAISS rollback |
| `app/services/presence_service.py` | asyncio.Lock, unified logging path |
| `app/services/recognition_service.py` | Increase detection FPS to 5-10 |
| `app/services/hls_service.py` | FFmpeg 30fps, 720p tuning |
| `app/routers/face.py` | Remove direct log_detection, feed tracking |
| `app/routers/live_stream.py` | WebSocket push rate tuning |
| `app/config.py` | New threshold params, streaming params |
| `app/main.py` | Startup reconciliation, periodic health check |

### Edge
| File | Changes |
|------|---------|
| `app/config.py` | FACE_CROP_SIZE 160, JPEG_QUALITY 85 |
| `app/processor.py` | Resize target 160x160 |
| `app/detector.py` | Confidence 0.6, min face size 80x80 |

### Mobile
| File | Changes |
|------|---------|
| `src/components/face/FaceScanCamera.tsx` | 160x160 minimum validation |
| `src/components/video/DetectionOverlay.tsx` | Animated overlay transitions |

### Documentation
| File | Changes |
|------|---------|
| `docs/main/ml-pipeline-spec.md` | New — authoritative ML spec |
| `docs/main/implementation.md` | Remove contradictions |
| `docs/main/technical-specification.md` | Align HTTP codes, image reqs |
| `docs/edge-device-integration-guide.md` | Reference ml-pipeline-spec |
