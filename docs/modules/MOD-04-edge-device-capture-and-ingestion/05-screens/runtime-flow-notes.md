# Runtime Flow Notes

## Edge Runtime Flow
1. Capture frame.
2. Detect face boxes.
3. Crop and compress faces.
4. Send payload to backend.
5. On send failure, enqueue payload.
6. Retry queue in background loop.

## Failure Recovery Flow
1. Backend unreachable detected.
2. Edge keeps capturing and queueing.
3. Retry interval attempts delivery.
4. On recovery, queued entries are drained.
