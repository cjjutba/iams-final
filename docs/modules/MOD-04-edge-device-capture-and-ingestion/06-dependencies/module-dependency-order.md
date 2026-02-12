# Module Dependency Order

## Upstream Dependencies for MOD-04
1. `MOD-03` Face Registration and Recognition
   - Required backend face-processing contract alignment (`POST /face/process`).
   - Shared API key auth middleware (`EDGE_API_KEY` validation).

2. Backend health/runtime availability
   - Required target endpoint reachability.

3. `EDGE_API_KEY` provisioning
   - API key must be generated and configured on both edge device and backend before edge can authenticate.

## MOD-04 Before/After Sequence
1. MOD-01 (Auth) → MOD-02 (Users) → MOD-03 (Face Recognition) → **MOD-04 (Edge Capture)**
2. Validate against `/face/process` backend contract with API key auth.
3. Integrate downstream with:
   - `MOD-06` attendance processing (backend uses recognition results)
   - `MOD-07` presence tracking (backend uses presence logs)

## Internal Function Dependency Order
1. `FUN-04-01` Capture frames
2. `FUN-04-02` Detect/crop faces (depends on FUN-04-01)
3. `FUN-04-03` Compress/send payloads (depends on FUN-04-02)
4. `FUN-04-04` Queue failed sends (depends on FUN-04-03)
5. `FUN-04-05` Retry queued sends (depends on FUN-04-04)

## Rationale
- Queue/retry logic depends on stable send path and payload schema.
- API key auth must be established before any edge→backend communication works.
- MOD-03 must define the `/face/process` contract before MOD-04 can implement the caller side.
