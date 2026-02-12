# Task Breakdown

## Task List
| Task ID | Function | Task | Owner/Agent |
|---|---|---|---|
| MOD8-T00 | Setup | Verify JWT auth middleware, MOD-06/07 event triggers, env var config | backend-core-specialist |
| MOD8-T01 | FUN-08-01 | Implement WebSocket endpoint with JWT auth (query param `token`, close codes 4001/4003) | websocket-specialist |
| MOD8-T02 | FUN-08-01 | Implement connection manager (register, evict, idempotent reconnect) | websocket-specialist |
| MOD8-T03 | FUN-08-02 | Implement `attendance_update` event builder and publisher | websocket-specialist |
| MOD8-T04 | FUN-08-03 | Implement `early_leave` event builder and publisher | websocket-specialist |
| MOD8-T05 | FUN-08-04 | Implement `session_end` event builder and publisher | websocket-specialist |
| MOD8-T06 | FUN-08-05 | Implement heartbeat/ping-pong, stale detection, cleanup | websocket-specialist |
| MOD8-T07 | SCR set | Integrate mobile screens with WebSocket service and Zustand store | websocket-mobile-specialist |
| MOD8-T08 | QA | Add WebSocket tests (unit + integration + scenario, including auth) | test-automation-specialist |
| MOD8-T09 | QA | Verify auth enforcement for all close code scenarios (4001/4003) | test-automation-specialist |
| MOD8-T10 | Docs | Update traceability and changelog | docs-writer |

## Done Definition per Task
- Code merged.
- Tests pass.
- Traceability row updated.
- Auth enforcement verified (close codes 4001/4003 for appropriate scenarios).
- Event payloads match documented schemas with timezone offsets.
- Related docs updated when behavior changes.
