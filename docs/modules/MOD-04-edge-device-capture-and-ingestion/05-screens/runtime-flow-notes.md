# Runtime Flow Notes

## Edge Runtime Flow
1. Initialize camera (picamera2/OpenCV, 640x480, 15 FPS).
2. Read `EDGE_API_KEY` from environment for auth header.
3. Capture frame.
4. Detect face boxes (MediaPipe).
5. Crop faces (~112x112) and compress (JPEG 70%).
6. Build payload and send to backend `POST /face/process` with `X-API-Key` header.
7. On send failure, enqueue payload (bounded queue: 500 max, 5-min TTL).
8. Retry queue in background loop (10s interval, 3 attempts per batch).

## Backend Processing (context only — not owned by MOD-04)
1. Backend validates `X-API-Key`.
2. Backend resizes crops to 160x160.
3. Backend runs recognition (MOD-03, FAISS search, threshold 0.6).
4. Backend updates attendance (MOD-06) and presence (MOD-07).
5. Backend returns processed/matched/unmatched summary to edge.

## Failure Recovery Flow
1. Backend unreachable detected (network error or timeout).
2. Edge keeps capturing and queueing (non-blocking).
3. Retry interval (10s) attempts delivery with `X-API-Key` header.
4. On recovery, queued entries are drained.
5. Expired entries (older than 5 min) are discarded before retry.

## Auth Failure Flow
1. Backend returns 401 (missing/invalid API key).
2. Edge logs auth failure.
3. Edge should NOT queue on auth failure (fix config, not retry).
