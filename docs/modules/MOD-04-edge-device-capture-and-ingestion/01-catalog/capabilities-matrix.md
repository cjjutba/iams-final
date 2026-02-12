# Capabilities Matrix

| Actor | Capability | Function ID(s) | Notes |
|---|---|---|---|
| Edge runtime | Capture frames | FUN-04-01 | 640x480 at 15 FPS via picamera2/OpenCV |
| Edge runtime | Detect/crop faces | FUN-04-02 | MediaPipe detector, crops ~112x112 via OpenCV |
| Edge runtime | Send payloads | FUN-04-03 | 1 face per request, `X-API-Key` header required |
| Edge runtime | Queue failed sends | FUN-04-04 | Bounded queue: 500 max, 5-min TTL, drop oldest |
| Edge runtime | Retry and recover delivery | FUN-04-05 | Non-blocking retry, 10s interval, 3 attempts per batch |
| Operations | Monitor queue depth and failures | FUN-04-04, FUN-04-05 | Logs/metrics required |

## Auth Note
Edge runtime includes `X-API-Key` header on every `POST /face/process` request. Backend validates against `EDGE_API_KEY` env var. No Supabase JWT is used.
