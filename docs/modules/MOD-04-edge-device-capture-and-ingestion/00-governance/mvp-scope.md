# MVP Scope

## In Scope
- Frame capture from Raspberry Pi camera.
- Face detection and crop generation.
- JPEG compression and send flow.
- Queue when server unavailable.
- Retry with bounded queue policy.

## Out of Scope
- Running FaceNet/FAISS recognition directly on edge.
- Attendance decision logic.
- Advanced edge fleet orchestration.

## MVP Constraints
- Queue max size: 500 (drop oldest if full).
- Queue TTL: 5 minutes.
- Retry interval: 10 seconds.
- Batch size on send: 1 face per request.

## MVP Gate Criteria
- `FUN-04-01` through `FUN-04-05` implemented and tested.
- Queue/retry behavior verified in server-down scenario.
- Capture loop remains stable under intermittent network failures.
