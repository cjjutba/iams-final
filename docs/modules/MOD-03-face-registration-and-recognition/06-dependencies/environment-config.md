# Environment Configuration

## Required Variables (Face Module Context)
- `FAISS_INDEX_PATH`
- `RECOGNITION_THRESHOLD`
- model path/config values for embedding generation
- runtime storage path for index persistence

## Configuration Rules
- Threshold must be configurable without code change.
- Index path should be writable in deployment environment.
- Missing critical config should fail fast.

## Validation Checklist
- Face service starts with loaded model and index.
- Threshold value is logged at startup (non-secret).
- Registration and recognition endpoints read active config correctly.
