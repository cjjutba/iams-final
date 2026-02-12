# Task Breakdown

## Task List
| Task ID | Function | Task | Owner/Agent |
|---|---|---|---|
| MOD4-T01 | Setup | Configure edge env vars and implement API key header injection | edge-device-specialist |
| MOD4-T02 | FUN-04-01 | Implement camera capture loop (picamera2/OpenCV, 640x480, 15 FPS) | edge-device-specialist |
| MOD4-T03 | FUN-04-02 | Implement MediaPipe detection and crop pipeline (~112x112) | edge-device-specialist |
| MOD4-T04 | FUN-04-03 | Implement sender with payload schema and `X-API-Key` header | edge-api-specialist |
| MOD4-T05 | FUN-04-04 | Implement bounded queue policy (500 max, 5-min TTL, drop oldest) | edge-device-specialist |
| MOD4-T06 | FUN-04-05 | Implement retry worker with policy controls and `X-API-Key` header | edge-api-specialist |
| MOD4-T07 | FUN-04-03 | Implement auth failure handling (401 → log, do NOT queue) | edge-api-specialist |
| MOD4-T08 | QA | Add queue/retry/auth integration tests | test-automation-specialist |
| MOD4-T09 | Docs | Update traceability and changelog | docs-writer |

## Done Definition per Task
- Code merged
- Tests pass
- Traceability row updated
- Related docs updated when behavior changes
