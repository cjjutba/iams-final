# Edge Capture and Ingestion Module Catalog

## Subdomains
1. Frame Capture
- Read frames from camera stream.

2. Face Detection and Cropping
- Detect face boxes and extract crops.

3. Payload Preparation
- Compress crops and package edge API payload.

4. Delivery and Retry
- Send payloads to backend and retry failures.

5. Queue Management
- Buffer unsent payloads with bounded queue semantics.

## Function Catalog
| Function ID | Name | Summary |
|---|---|---|
| FUN-04-01 | Capture Frames | Acquire frames from camera source |
| FUN-04-02 | Detect and Crop Faces | Produce face crops and metadata |
| FUN-04-03 | Compress and Send | Package and transmit face payload |
| FUN-04-04 | Queue Unsent Data | Buffer payloads when backend unavailable |
| FUN-04-05 | Retry with Bounded Policy | Drain queue safely with retry limits |

## Actors
- Edge runtime service (RPi)
- Backend ingestion endpoint
- Operations maintainer

## Interfaces
- Camera driver/device
- HTTP client to backend `/face/process`
- In-memory queue and local logs
