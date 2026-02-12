# Environment Configuration

## Required Variables (Edge Context)
| Variable | Description | Example |
|---|---|---|
| `EDGE_SERVER_URL` | Backend base URL | `http://192.168.1.100:8000/api/v1` |
| `EDGE_API_KEY` | Shared API key for `X-API-Key` header authentication | `sk-edge-...` |
| `ROOM_ID` | Room/session identifier for this edge device | `uuid` |
| `CAMERA_RESOLUTION` | Frame resolution | `640x480` |
| `CAMERA_FPS` | Frame rate | `15` |
| `QUEUE_MAX_SIZE` | Max items in offline queue | `500` |
| `QUEUE_TTL_SECONDS` | Max age of queued items in seconds | `300` |
| `RETRY_INTERVAL_SECONDS` | Delay between retry rounds | `10` |
| `RETRY_MAX_ATTEMPTS` | Max retry attempts per batch | `3` |

## Configuration Rules
- Backend URL must be reachable from edge network.
- `EDGE_API_KEY` must match the value configured on the backend (`EDGE_API_KEY` env var).
- Queue limits should be explicit and not unlimited.
- Missing critical config (`EDGE_SERVER_URL`, `EDGE_API_KEY`) should fail fast on startup.

## Security Rules
- **Never commit `EDGE_API_KEY` to source control.**
- `EDGE_API_KEY` should be shared securely between backend and edge during provisioning.
- Do not log `EDGE_API_KEY` value in startup logs.

## Validation Checklist
- [ ] Edge service starts with valid env (all required variables present).
- [ ] `EDGE_API_KEY` is set and matches backend.
- [ ] Payload target endpoint resolved correctly.
- [ ] `POST /face/process` returns 200 with valid API key (not 401).
- [ ] Runtime logs include effective config summary (non-secret values only).
