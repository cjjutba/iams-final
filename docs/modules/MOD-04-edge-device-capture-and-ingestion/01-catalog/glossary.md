# Glossary

- **Edge Device:** Raspberry Pi runtime that captures and sends face data to backend.
- **Face Crop:** Extracted face image from full frame, cropped at ~112x112 pixels on edge.
- **Queue TTL:** Maximum age of unsent payload before discard (5 minutes).
- **Retry Interval:** Delay between resend attempts (10 seconds).
- **Batch Size:** Number of faces sent per request (1 face per request).
- **Non-blocking Retry:** Retry behavior that does not pause frame capture loop.
- **API Key (Edge Auth):** Shared secret sent via `X-API-Key` header to authenticate edge→backend requests. Validated against `EDGE_API_KEY` env var on backend.
- **MediaPipe:** Google face detection model used on edge for detecting face bounding boxes. Lightweight enough for RPi.
- **picamera2:** Python library for Raspberry Pi camera module. Used for frame capture.
- **Model Input Resize:** Backend responsibility to resize edge crops (~112x112) to 160x160 before FaceNet inference. Edge does NOT resize to model input size.
- **JPEG Compression:** Face crops are compressed to JPEG at 70% quality before transmission to reduce payload size.
- **collections.deque:** Python standard library bounded queue used for offline payload buffering (`maxlen=500`).
