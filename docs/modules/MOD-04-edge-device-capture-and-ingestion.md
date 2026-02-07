# MOD-04: Edge Device Capture and Ingestion

This file is a module-level source of truth derived from `docs/main/master-blueprint.md` section 6.
Update both files together when module scope changes.

## Specification

Purpose:
- Capture classroom frames, detect faces, and send face crops to backend.

Functions:
- `FUN-04-01`: Capture frames from camera.
- `FUN-04-02`: Detect and crop faces.
- `FUN-04-03`: Compress and send crops to backend.
- `FUN-04-04`: Queue unsent data when backend is unreachable.
- `FUN-04-05`: Retry with bounded queue policy.

API Contracts:
- `POST /face/process`

Data:
- Local edge queue (in-memory bounded queue)
- Optional local logs

Screens:
- None (edge runtime module)

Done Criteria:
- Queue max size and TTL policy enforced.
- Retry behavior does not block frame capture loop.
- Errors and queue depth are logged.


## Implementation Rule
- Implement only the listed `FUN-*` items for this module when this doc is referenced.
- If scope/API/data/screen changes are needed, update docs first before code.
