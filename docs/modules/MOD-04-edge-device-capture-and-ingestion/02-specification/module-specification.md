# Module Specification

## Module ID
`MOD-04`

## Purpose
Capture classroom frames, detect faces, and send face crops to backend.

## Core Functions
- `FUN-04-01`: Capture frames from camera.
- `FUN-04-02`: Detect and crop faces.
- `FUN-04-03`: Compress and send crops to backend.
- `FUN-04-04`: Queue unsent data when backend is unreachable.
- `FUN-04-05`: Retry with bounded queue policy.

## API Contracts
- `POST /face/process`

## Data Dependencies
- Local edge queue (in-memory bounded queue)
- Optional local logs

## Screen Dependencies
- None (edge runtime module)

## Done Criteria
- Queue max size and TTL policy enforced.
- Retry behavior does not block frame capture loop.
- Errors and queue depth are logged.
