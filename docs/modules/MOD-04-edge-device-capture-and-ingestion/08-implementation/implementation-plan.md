# Implementation Plan (MOD-04)

## Phase 1: Foundations
- Configure edge environment variables (`EDGE_SERVER_URL`, `EDGE_API_KEY`, `ROOM_ID`, camera/queue settings).
- Implement API key header injection (read `EDGE_API_KEY`, set `X-API-Key` header on all outbound requests).
- Verify backend API key validation middleware is in place (shared with MOD-03).

## Phase 2: Capture Pipeline
- Implement camera capture loop (picamera2/OpenCV, 640x480, 15 FPS).
- Implement MediaPipe face detection and crop stages (~112x112).
- Verify crop size is ~112x112 (NOT 160x160 — backend handles resize).

## Phase 3: Sender Pipeline
- Implement JPEG compression (70% quality) and Base64 encoding.
- Implement payload builder matching `/face/process` contract.
- Implement send function with `X-API-Key` header.
- Handle 401 responses (log, do NOT queue for retry).

## Phase 4: Reliability Layer
- Implement bounded queue model (`collections.deque(maxlen=500)`).
- Implement TTL discard policy (5 minutes).
- Implement retry worker with policy controls (10s interval, 3 attempts per batch).
- Ensure retry requests include `X-API-Key` header.

## Phase 5: Runtime Hardening
- Add camera reconnect/restart behavior (retry every 5s).
- Add auth failure detection and logging.
- Add logging (queue depth, drops, send success/failure, auth failures).
- Validate resource usage boundaries on RPi.

## Phase 6: Validation
- Run unit/integration/scenario tests (including API key auth scenarios).
- Validate acceptance criteria and update traceability.
- Verify auth failure handling (401 logged, not queued).
- Verify idempotency handling for retry scenarios.
