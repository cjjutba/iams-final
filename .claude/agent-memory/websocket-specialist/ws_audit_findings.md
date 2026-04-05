---
name: WebSocket Audit Findings (2026-03-30)
description: Comprehensive audit of IAMS WebSocket system — 22 issues found across backend router, Android client, presence integration, and concurrency
type: project
---

## Key Findings

**Critical:**
- No JWT authentication on either WS endpoint (websocket.py lines 160-181)
- Android client sends no auth token (AttendanceWebSocketClient.kt line 70)

**High — Reliability:**
- Unhandled exceptions in WS handler leak dead connections (only WebSocketDisconnect caught)
- Double delivery in multi-worker: local send + Redis subscriber both deliver to same clients
- Sync `redis.Redis` (not async) in presence_service._get_identified_users_from_pipeline blocks event loop
- Sync SQLAlchemy calls inside asyncio Lock in process_session_scan blocks event loop
- DB session in realtime_pipeline spans entire class session (hours)
- TrackPresenceService early_leave events are broadcast but never persisted to DB or emailed

**Medium — Android Client:**
- OkHttpClient threads leak on destroy() — no dispatcher/connection pool cleanup
- No reconnect on server-initiated close (onClosed), only on failure
- Rapid connect() can orphan previous WebSocket instance
- No Android client exists for /alerts/{user_id} endpoint

**Medium — Data:**
- confidence vs similarity key mismatch in presence_service (line 482 reads "similarity" but dict has "confidence")
- schedule_repo.get_by_id called every frame at 10fps — should cache

**How to apply:** When fixing, prioritize auth first (security), then event-loop-blocking issues (system stability), then Android client lifecycle bugs (user experience).
