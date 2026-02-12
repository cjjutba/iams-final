# Function Specifications

## FUN-04-01 Capture Frames
Goal:
- Acquire frames from camera at configured FPS (15) and resolution (640x480).

Inputs:
- Camera stream/device handle (picamera2 or OpenCV).

Process:
1. Initialize camera driver (picamera2 preferred on RPi, OpenCV fallback).
2. Configure resolution to 640x480 and frame rate to 15 FPS.
3. Read frames continuously.
4. Attach capture timestamp metadata (ISO 8601).

Outputs:
- Raw frame stream for detection stage.

Validation Rules:
- Recover from camera disconnect with retry policy (retry every 5 seconds).
- Skip invalid/corrupt frame data safely.

## FUN-04-02 Detect and Crop Faces
Goal:
- Detect face bounding boxes and produce normalized face crops.

Inputs:
- Raw frame (640x480) and timestamp.

Process:
1. Run MediaPipe face detector on frame.
2. Extract bounding boxes `[x, y, w, h]` for each detected face.
3. Crop faces from frame at detection output size (~112x112).
4. Produce bbox metadata for each crop.

Outputs:
- Face crop list (~112x112 each) and bbox metadata.

Validation Rules:
- Ignore frames without detected faces.
- Ensure minimum crop quality constraints (not too small, not clipped at edges).

Resize Boundary:
- Edge crops at ~112x112 (detection output size).
- Backend handles final resize to 160x160 for FaceNet model input.
- Edge does NOT resize to 160x160.

## FUN-04-03 Compress and Send
Goal:
- Compress face crops and send payload to backend ingestion endpoint with API key authentication.

Inputs:
- Face crops (~112x112) + metadata (`room_id`, `timestamp`).

Process:
1. JPEG compress each face crop at 70% quality.
2. Base64-encode compressed JPEG bytes.
3. Build API payload matching `/face/process` contract.
4. Set `X-API-Key` header from `EDGE_API_KEY` environment variable.
5. POST to `/face/process`.
6. Record response outcome (success/failure, matched/unmatched counts).

Outputs:
- Send success/failure status.

Validation Rules:
- Payload schema must match API contract.
- `X-API-Key` header must be present on every request.
- Handle transient network errors gracefully (route to queue on failure).

## FUN-04-04 Queue Unsent Data
Goal:
- Buffer failed payloads to avoid data loss during connectivity issues.

Inputs:
- Failed payloads and enqueue timestamp.

Process:
1. Add failed payload to bounded queue (`collections.deque(maxlen=500)`).
2. Enforce max-size (500) and drop-oldest policy.
3. Enforce TTL discard policy (5 minutes).
4. Track queue depth and drops in logs.

Outputs:
- Updated queue state.

Validation Rules:
- Queue size hard limit (500) respected at all times.
- Expired items (older than 5 minutes) removed before retry.

## FUN-04-05 Retry with Bounded Policy
Goal:
- Retry queued payload delivery without blocking capture loop.

Inputs:
- Queued payloads and retry configuration (10s interval, 3 max attempts per batch).

Process:
1. Periodically attempt send from queue (every 10 seconds).
2. Include `X-API-Key` header on retry requests.
3. Apply retry max attempts (3 per batch).
4. Requeue failed payloads as needed.
5. Remove successfully delivered payloads.

Outputs:
- Queue drain progress and retry outcome.

Validation Rules:
- Retry interval (10 seconds) and max-attempt (3) policy must be enforced.
- Capture pipeline remains responsive while retries run (non-blocking).

Idempotency Note:
- Edge may retry sending the same face crop multiple times due to transient failures. Backend `/face/process` should handle this gracefully. MOD-06 attendance logic should ensure duplicate detections from the same timestamp are not counted twice.
