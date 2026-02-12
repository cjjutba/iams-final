# Edge Capture and Ingestion Module Catalog

## Auth Context
Edge devices authenticate with backend using a shared API key (`X-API-Key` header, validated against `EDGE_API_KEY`). No Supabase JWT is used on the edge side.

## Subdomains
1. Frame Capture
- Read frames from camera stream (640x480, 15 FPS).

2. Face Detection and Cropping
- Detect face boxes (MediaPipe) and extract crops (~112x112).

3. Payload Preparation
- Compress crops (JPEG 70%) and package edge API payload.

4. Delivery and Retry
- Send payloads to backend with `X-API-Key` header and retry failures.

5. Queue Management
- Buffer unsent payloads with bounded queue semantics (500 max, 5-min TTL).

## Function Catalog
| Function ID | Name | Summary |
|---|---|---|
| FUN-04-01 | Capture Frames | Acquire frames from camera source (640x480, 15 FPS) |
| FUN-04-02 | Detect and Crop Faces | Produce face crops (~112x112) and bbox metadata via MediaPipe |
| FUN-04-03 | Compress and Send | JPEG compress, package payload, POST to `/face/process` with API key |
| FUN-04-04 | Queue Unsent Data | Buffer payloads when backend unavailable (max 500, 5-min TTL) |
| FUN-04-05 | Retry with Bounded Policy | Drain queue safely with retry limits (10s interval, 3 attempts) |

## Actors
- Edge runtime service (RPi)
- Backend ingestion endpoint (`POST /face/process`)
- Operations maintainer

## Interfaces
- Camera driver/device (picamera2/OpenCV)
- MediaPipe face detector
- HTTP client to backend `/face/process` (httpx with `X-API-Key` header)
- In-memory queue (`collections.deque(maxlen=500)`) and local logs
