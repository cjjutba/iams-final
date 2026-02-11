# Environment Configuration

## Required Variables (Face Module Context)
| Variable | Purpose | Example |
|---|---|---|
| `FAISS_INDEX_PATH` | Path to FAISS index file on disk | `./data/faiss_index.bin` |
| `RECOGNITION_THRESHOLD` | Cosine similarity threshold for face matching | `0.6` |
| `FACENET_MODEL_PATH` | Path to FaceNet model weights | `./models/facenet.pt` |
| `EDGE_API_KEY` | Shared API key for edge device authentication | `your-secret-api-key` |
| `DATABASE_URL` | PostgreSQL connection (Supabase) | `postgresql://user:pass@host/db` |
| `SUPABASE_URL` | Supabase project URL | `https://xxxxx.supabase.co` |
| `SUPABASE_JWT_SECRET` | Secret for verifying Supabase-issued JWTs | `your-jwt-secret` |

## Configuration Rules
- Threshold must be configurable without code change (via `RECOGNITION_THRESHOLD`).
- Index path should be writable in deployment environment.
- Missing critical config should fail fast at startup.
- `EDGE_API_KEY` must never be committed to source control.
- `SUPABASE_JWT_SECRET` is shared with MOD-01 middleware.

## Validation Checklist
- Face service starts with loaded model and index.
- Threshold value is logged at startup (non-secret).
- Registration and recognition endpoints read active config correctly.
- API key validation is active on recognize endpoint.
- Supabase JWT middleware is active on register and status endpoints.
