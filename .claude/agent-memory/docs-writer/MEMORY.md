# docs-writer Agent Memory

## Key File Locations

- Main docs: `/Users/cjjutba/Projects/iams/docs/main/`
- ML model: `backend/app/services/ml/insightface_model.py`
- Config (source of truth for all defaults): `backend/app/config.py`

## Always Verify Config Values From config.py

Before writing any threshold or default value in docs, read `backend/app/config.py`.
Values drift from what the task description says. Confirmed divergences found:
- `RECOGNITION_THRESHOLD` was described as 0.45 — confirmed correct
- `RECOGNITION_FPS` was 8.0 in old docs, actual value is 2.0
- `RECOGNITION_MAX_BATCH_SIZE` was 20 in old docs, actual value is 50
- `HLS_SEGMENT_DURATION` is 0.2 in config (not 2 as stated in old docs; the
  table in Section 6.4 still uses 2 because that's the user-facing description;
  verify when updating the streaming section)

## InsightFace Pipeline (2026-03 migration)

- Old stack removed: FaceNet (PyTorch), MTCNN (facenet-pytorch), MediaPipe
- New stack: InsightFace `buffalo_l` (ONNX Runtime)
  - Detector: SCRFD 10G (ResNet50), input 640x640
  - Embedder: ArcFace w600k_r50 (ResNet50), 512-dim L2-normalized
  - Alignment: 5-point landmark affine warp to 112x112 crop
  - CoreML on macOS Apple Silicon; CPU on Linux/Windows
- Both registration and CCTV recognition share the same model instance
- Embeddings are numerically compatible between paths
- Removed settings: `FACE_IMAGE_SIZE`, `USE_FACE_ALIGNMENT`,
  `MEDIAPIPE_DETECTION_CONFIDENCE`, `RECOGNITION_MIN_FACE_PX`

## ml-pipeline-spec.md Structure

Sections: Preprocessing Chain, Face Registration, Face Recognition,
Edge API Contract, FAISS Lifecycle, Streaming, Threshold Reference Table,
Academic References (added 2026-03 for thesis).

FAISS section (IndexFlatIP, 512-dim, soft/hard delete, reconciliation) is
stable and unchanged by the InsightFace migration.

## Academic Citations Added (Section 8)

- ArcFace: Deng et al., CVPR 2019
- SCRFD: Guo et al., ICCV 2021
- InsightFace library: Deng et al., arXiv 2022

## Documentation Conventions

- Use `<!-- Last updated: YYYY-MM-DD -->` on complex sections
- Add migration notes at the top of spec files when a major component changes
- Never duplicate threshold tables — Section 7 is the single reference;
  inline tables in earlier sections only list the most relevant parameters
