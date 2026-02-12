# Integration Points

## Edge Runtime Integrations
- Camera SDK/driver (picamera2 preferred on RPi, OpenCV fallback)
- Face detector model/runtime (MediaPipe Face Detector)
- HTTP client for backend send (httpx or equivalent)

## MediaPipe Face Detector Configuration
- **Model:** MediaPipe Face Detector (short-range model for close-up detection)
- **Input:** Raw frame from camera (640x480)
- **Output:** Bounding boxes `[x, y, w, h]` for each detected face
- **Detection confidence threshold:** Configurable (default ~0.5)
- **Platform:** Runs on RPi ARM architecture (TFLite backend)

## Backend Integrations
- `POST /face/process` endpoint contract
- API key authentication (`X-API-Key` header, validated against `EDGE_API_KEY`)
- Backend health and network routing

## Auth Integration Details
- Edge reads `EDGE_API_KEY` from environment on startup.
- Every `POST /face/process` request includes `X-API-Key: <key>` header.
- Backend validates using the same API key middleware as MOD-03 `POST /face/recognize`.
- On 401 response: edge logs auth failure, does NOT queue for retry (config issue).

## MOD-03 Recognition Coordination
- Edge sends cropped faces to `POST /face/process` (owned as caller by MOD-04).
- Backend internally routes payload to recognition service (MOD-03).
- Edge does NOT call `POST /face/recognize` directly.
- Backend handles resize to 160x160 before FaceNet inference.

## MOD-06/MOD-07 Downstream Integration
- Backend uses matched user IDs from recognition to mark attendance (MOD-06).
- MOD-07 uses presence logs from MOD-06 to track consecutive misses and flag early leave.
- Edge device does not directly participate in MOD-06 or MOD-07 logic.

## MOD-02 User Deletion Coordination
- When a user is deleted (MOD-02), MOD-03 removes their face registration from FAISS.
- Edge has no direct notification of user deletion.
- If edge sends queued faces of a deleted user, backend returns "unmatched" (graceful degradation).
- No special edge handling required — edge continues operating normally.

## Deployment Integrations
- systemd auto-restart behavior
- Edge `.env` configuration (EDGE_SERVER_URL, EDGE_API_KEY, ROOM_ID)
- WiFi/network reachability to backend
