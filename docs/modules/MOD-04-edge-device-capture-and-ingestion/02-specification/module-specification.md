# Module Specification

## Module ID
`MOD-04`

## Purpose
Capture classroom frames, detect faces, and send face crops to backend for recognition and attendance processing.

## Auth Context
Edge device authenticates with backend via shared API key (`X-API-Key` header, validated against `EDGE_API_KEY` env var). No Supabase JWT is used on the edge device.

## Core Functions
- `FUN-04-01`: Capture frames from camera (640x480, 15 FPS).
- `FUN-04-02`: Detect (MediaPipe) and crop faces (~112x112).
- `FUN-04-03`: Compress (JPEG 70%) and send crops to backend with API key auth.
- `FUN-04-04`: Queue unsent data when backend is unreachable (500 max, 5-min TTL).
- `FUN-04-05`: Retry with bounded queue policy (10s interval, 3 attempts per batch).

## API Contracts
- `POST /face/process` — protected by `X-API-Key` header

## Data Dependencies
- Local edge queue (in-memory bounded queue: `collections.deque(maxlen=500)`)
- Optional local logs

## Screen Dependencies
- None (edge runtime module)

## Cross-Module Coordination
- **MOD-03:** Backend internally routes `/face/process` payload to recognition service (`POST /face/recognize`). Edge does not call `/face/recognize` directly.
- **MOD-06/MOD-07:** Backend uses recognition results to update attendance and presence records. Edge is not involved in attendance logic.
- **MOD-02 User Deletion:** If a user is deleted while edge has queued data, backend will return "unmatched" for that user's face. No special edge handling required.

## Done Criteria
- Queue max size and TTL policy enforced.
- Retry behavior does not block frame capture loop.
- Errors and queue depth are logged.
- `X-API-Key` header included on every backend request.
- API key auth verified (401 on missing/invalid key).
- Edge crops at ~112x112; does not resize to 160x160 (backend responsibility).
