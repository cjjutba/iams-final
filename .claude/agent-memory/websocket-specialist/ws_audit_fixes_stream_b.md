---
name: Stream B Audit Fixes Applied
description: WebSocket JWT auth, iteration safety, double-delivery prevention, short-lived DB sessions, schedule caching, early leave persistence
type: project
---

Applied 2026-03-30 on feat/architecture-redesign branch.

## Changes Made

### websocket.py (B1, B2, B3)
- **JWT auth**: Both `/attendance/{schedule_id}` and `/alerts/{user_id}` now extract `token` from query params, call `verify_token()`, close with 4001 on failure. Alerts endpoint also verifies `payload["user_id"]` matches path param (close 4003 if mismatch).
- **finally blocks**: Both endpoints use `finally` for `remove_*_client()` instead of only catching `WebSocketDisconnect`.
- **Iteration safety**: All three iteration points (`broadcast_attendance`, `broadcast_alert`, `_redis_subscribe_loop`) now use `list()` snapshot before iterating over client sets.
- **Double delivery**: `_redis_publish` includes `"origin_pid": os.getpid()` in published message. `_redis_subscribe_loop` skips messages where `origin_pid` matches current PID.
- **Logging**: Bare `pass` in `_redis_publish` except block replaced with `logger.warning`.

### realtime_pipeline.py (B4)
- **Short-lived DB sessions**: `start()` now closes the setup DB session in a `finally` before launching the loop task. `_run_loop()` takes no DB arg; creates short-lived sessions via `self._db_factory()` for: (a) every `process_track_frame` call (event-driven writes), (b) periodic `flush_presence_logs`, and (c) `end_session` in `stop()`.
- **rebind_db pattern**: `TrackPresenceService.rebind_db(db)` swaps the session and all repos. Called before each short-lived DB usage.

### track_presence_service.py (B5)
- **Schedule caching**: `start_session()` stores `self._schedule`. `process_track_frame()` uses `self._schedule.start_time` instead of re-querying every frame.
- **EarlyLeaveEvent persistence**: After updating attendance status to EARLY_LEAVE, creates and commits an `EarlyLeaveEvent` record with `attendance_id`, `detected_at`, `last_seen_at`, `consecutive_misses` (derived from absent_seconds / SCAN_INTERVAL_SECONDS), and `context_severity="auto_detected"`.
- **rebind_db method**: New method to swap DB session and rebuild all repository instances.

## Key Technical Details
- JWT payload uses `"user_id"` key (not `"sub"`)
- `verify_token()` raises `AuthenticationError` (from `app.utils.exceptions`)
- `EarlyLeaveEvent` requires `last_seen_at` (non-nullable), so we fall back to `check_in_time` or `datetime.now()`
- `SCAN_INTERVAL_SECONDS = 15` in settings — used to convert absence duration to scan-equivalent consecutive_misses
