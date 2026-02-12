# MVP Scope

## In Scope
- Frame capture from Raspberry Pi camera (640x480, 15 FPS via picamera2/OpenCV).
- Face detection (MediaPipe) and crop generation (~112x112).
- JPEG compression (70% quality) and send flow with API key authentication.
- Queue when server unavailable (bounded in-memory queue).
- Retry with bounded queue policy.

## Out of Scope
- Running FaceNet/FAISS recognition directly on edge (backend responsibility).
- Attendance decision logic (MOD-06/MOD-07).
- Advanced edge fleet orchestration.
- Rate limiting (thesis demonstration).
- Resizing crops to 160x160 (backend handles this before FaceNet inference).

## MVP Constraints
- Queue max size: 500 (drop oldest if full) — `collections.deque(maxlen=500)`.
- Queue TTL: 5 minutes.
- Retry interval: 10 seconds.
- Retry max attempts: 3 per batch.
- Batch size on send: 1 face per request.
- Edge crop size: ~112x112 (intermediate; backend resizes to 160x160).
- Auth: shared API key via `X-API-Key` header (NOT Supabase JWT).

## MVP Gate Criteria
- `FUN-04-01` through `FUN-04-05` implemented and tested.
- Queue/retry behavior verified in server-down scenario.
- Capture loop remains stable under intermittent network failures.
- `X-API-Key` header sent on every `POST /face/process` request.
- API key authentication verified (401 on missing/invalid key).
