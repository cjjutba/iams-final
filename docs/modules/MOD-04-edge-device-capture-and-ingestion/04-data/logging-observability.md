# Logging and Observability

## Required Log Events
- Camera init/reconnect attempts
- Send success/failure (with HTTP status code)
- Auth failure (401 from backend)
- Queue enqueue/dequeue
- Queue drop due to overflow/TTL
- Retry cycle summary

## Minimum Metrics
- Current queue depth
- Dropped payload count
- Send success rate
- Retry attempts per minute
- Auth failure count (401 responses)

## Logging Rules
- Avoid logging raw image content (base64 payload).
- Include correlation/timestamp fields for diagnostics.
- Keep logs rotation-friendly on constrained storage (RPi SD card).
- Log effective config summary on startup (non-secret values only; do NOT log `EDGE_API_KEY`).
