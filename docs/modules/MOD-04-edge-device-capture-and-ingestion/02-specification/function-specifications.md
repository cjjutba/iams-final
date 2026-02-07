# Function Specifications

## FUN-04-01 Capture Frames
Goal:
- Acquire frames from camera at configured FPS/resolution.

Inputs:
- Camera stream/device handle.

Process:
1. Initialize camera driver.
2. Read frames continuously.
3. Attach capture timestamp metadata.

Outputs:
- Raw frame stream for detection stage.

Validation Rules:
- Recover from camera disconnect with retry policy.
- Skip invalid/corrupt frame data safely.

## FUN-04-02 Detect and Crop Faces
Goal:
- Detect face bounding boxes and produce normalized face crops.

Inputs:
- Raw frame and timestamp.

Process:
1. Run face detector.
2. Extract bounding boxes.
3. Crop faces and resize to target dimensions.
4. Produce optional bbox metadata.

Outputs:
- Face crop list and bbox metadata.

Validation Rules:
- Ignore frames without faces.
- Ensure minimum crop quality constraints.

## FUN-04-03 Compress and Send
Goal:
- Compress face crops and send payload to backend ingestion endpoint.

Inputs:
- Face crops + metadata (`room_id`, `timestamp`).

Process:
1. JPEG compress image(s).
2. Build API payload.
3. POST to `/face/process`.
4. Record response outcome.

Outputs:
- Send success/failure status.

Validation Rules:
- Payload schema must match API contract.
- Handle transient network errors gracefully.

## FUN-04-04 Queue Unsent Data
Goal:
- Buffer failed payloads to avoid data loss during connectivity issues.

Inputs:
- Failed payloads and enqueue timestamp.

Process:
1. Add failed payload to bounded queue.
2. Enforce max-size and drop-oldest policy.
3. Enforce TTL discard policy.
4. Track queue depth and drops in logs.

Outputs:
- Updated queue state.

Validation Rules:
- Queue size hard limit respected.
- Expired items removed before retry.

## FUN-04-05 Retry with Bounded Policy
Goal:
- Retry queued payload delivery without blocking capture loop.

Inputs:
- Queued payloads and retry configuration.

Process:
1. Periodically attempt send from queue.
2. Apply retry max attempts per batch.
3. Requeue failed payloads as needed.
4. Remove successfully delivered payloads.

Outputs:
- Queue drain progress and retry outcome.

Validation Rules:
- Retry interval and max-attempt policy must be enforced.
- Capture pipeline remains responsive while retries run.
