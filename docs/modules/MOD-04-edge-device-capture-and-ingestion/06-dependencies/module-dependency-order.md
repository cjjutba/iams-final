# Module Dependency Order

## Upstream Dependencies for MOD-04
1. `MOD-03` Face Registration and Recognition
- Required backend face-processing contract alignment.

2. Backend health/runtime availability
- Required target endpoint reachability.

## MOD-04 Before/After Sequence
1. Implement core edge capture and sender pipeline.
2. Validate against `/face/process` backend contract.
3. Integrate downstream with:
- `MOD-06` attendance processing
- `MOD-07` presence tracking

## Internal Function Dependency Order
1. `FUN-04-01` Capture frames
2. `FUN-04-02` Detect/crop faces
3. `FUN-04-03` Compress/send payloads
4. `FUN-04-04` Queue failed sends
5. `FUN-04-05` Retry queued sends

## Rationale
Queue/retry logic depends on stable send path and payload schema.
