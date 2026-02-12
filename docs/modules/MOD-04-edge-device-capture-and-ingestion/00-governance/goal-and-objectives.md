# Goal and Objectives

## Module Goal
Capture classroom frames on edge device, detect/crop faces, and reliably deliver ingestion payloads to backend `/face/process` even during transient connectivity failures. Edge authenticates with a shared API key (`X-API-Key` header), not Supabase JWT.

## Primary Objectives
1. Capture frames at configured resolution (640x480) and FPS (15).
2. Detect faces using MediaPipe and crop at intermediate size (~112x112).
3. Compress (JPEG 70%) and transmit payloads to backend `POST /face/process` with API key auth.
4. Queue unsent payloads when backend is unavailable (bounded queue: 500 items, 5-min TTL).
5. Retry safely with bounded queue policy (10s interval, 3 attempts per batch) and clear observability.
6. Maintain crop size boundary: edge crops ~112x112, backend handles resize to 160x160 for FaceNet model input.

## Success Outcomes
- Edge pipeline runs continuously without blocking capture loop.
- Queue policy prevents memory overflow and supports eventual delivery.
- Payloads conform to documented edge API schema with valid `X-API-Key` header.
- Recovery behavior is deterministic on disconnect/restart failures.

## Non-Goals (for MOD-04 MVP)
- Face recognition model inference on edge device (backend responsibility via MOD-03).
- Attendance or presence business logic (MOD-06/MOD-07).
- Multi-node edge orchestration.
- Rate limiting (thesis demonstration).

## Stakeholders
- Classroom operations (device reliability).
- Backend ingestion service consumers (MOD-03 recognition, MOD-06 attendance).
- Edge implementers and maintainers.
