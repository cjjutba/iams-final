# Goal and Objectives

## Module Goal
Capture classroom frames on edge device, detect/crop faces, and reliably deliver ingestion payloads to backend even during transient connectivity failures.

## Primary Objectives
1. Capture frames at configured resolution/FPS.
2. Detect and crop faces from each frame.
3. Compress and transmit payloads to backend `/face/process` contract.
4. Queue unsent payloads when backend is unavailable.
5. Retry safely with bounded queue policy and clear observability.

## Success Outcomes
- Edge pipeline runs continuously without blocking capture loop.
- Queue policy prevents memory overflow and supports eventual delivery.
- Payloads conform to documented edge API schema.
- Recovery behavior is deterministic on disconnect/restart failures.

## Non-Goals (for MOD-04 MVP)
- Face recognition model inference on edge device.
- Attendance or presence business logic.
- Multi-node edge orchestration.

## Stakeholders
- Classroom operations (device reliability).
- Backend ingestion service consumers.
- Edge implementers and maintainers.
