# Folder and File Mapping

## Edge Expected Touchpoints
- `edge/app/main.py` — Entry point, runtime loop
- `edge/app/camera.py` — Camera capture (picamera2/OpenCV, 640x480, 15 FPS)
- `edge/app/detector.py` — MediaPipe face detection
- `edge/app/processor.py` — Crop (~112x112), compress (JPEG 70%), Base64 encode
- `edge/app/sender.py` — HTTP client with `X-API-Key` header, send to `/face/process`
- `edge/app/queue_manager.py` — Bounded queue (`collections.deque(maxlen=500)`), TTL, retry
- `edge/app/config.py` — `EDGE_SERVER_URL`, `EDGE_API_KEY`, `ROOM_ID`, camera/queue config

## Backend Contract Touchpoint
- `backend/app/routers/face.py` — `/face/process` handler (receives edge payloads)
- `backend/app/utils/dependencies.py` — API key validation middleware (shared with MOD-03)

## Docs to Keep in Sync
- `docs/main/architecture.md`
- `docs/main/implementation.md`
- `docs/main/api-reference.md`
- `docs/main/database-schema.md`
- `docs/modules/MOD-04-edge-device-capture-and-ingestion/`
