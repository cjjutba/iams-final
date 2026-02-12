# Implementation Plan (MOD-08)

## Phase 0: Foundations
- Verify MOD-01 JWT auth middleware (`get_current_user`) is in place and working.
- Verify MOD-06 attendance service and MOD-07 presence service are stable and can emit events.
- Verify schedule/enrollment data available from MOD-05 for recipient resolution.
- Configure env vars: `WS_HEARTBEAT_INTERVAL`, `WS_STALE_TIMEOUT`, `WS_MAX_CONNECTIONS_PER_USER`, `TIMEZONE`.
- Set up WebSocket router skeleton at `/ws/{user_id}`.

## Phase 1: Connection Foundation
- Implement authenticated `WS /ws/{user_id}` endpoint with JWT validation via `token` query parameter.
- Implement close code 4001 (Unauthorized) and 4003 (Forbidden).
- Add connection manager with in-memory map registration/removal.
- Implement idempotent reconnect: evict stale entry before registering new socket.

## Phase 2: Event Publishing Pipeline
- Implement event envelope builders for:
  - `attendance_update` (required: `student_id`, `schedule_id`, `status`, `timestamp`)
  - `early_leave` (required: `student_id`, `schedule_id`, `detected_at`)
  - `session_end` (required: `schedule_id`, `summary`)
- Ensure all timestamps use `TIMEZONE` (Asia/Manila, +08:00) in ISO-8601 format.
- Wire publisher calls from:
  - `attendance_service.py` (MOD-06) → FUN-08-02
  - `presence_service.py` (MOD-07) → FUN-08-03
  - Session finalization flow → FUN-08-04

## Phase 3: Reliability Controls
- Add heartbeat ping/pong at `WS_HEARTBEAT_INTERVAL` (default: 30s).
- Add stale connection detection at `WS_STALE_TIMEOUT` (default: 60s).
- Enforce `WS_MAX_CONNECTIONS_PER_USER` cap.
- Add reconnect-safe handling to avoid duplicate stale entries.
- Implement send failure logging (no silent drops).

## Phase 4: Mobile Integration
- Integrate `websocketService.ts` with target screens (SCR-018, SCR-021, SCR-025, SCR-029).
- Map event types to UI actions/state updates via Zustand store.
- Add connection-state indicators (reconnecting badge).
- Handle auth errors: close code 4001 → redirect to login, 4003 → show error.
- Add exponential backoff reconnect (`WS_RECONNECT_BASE_DELAY_MS` to `WS_RECONNECT_MAX_DELAY_MS`).

## Phase 5: Validation and Hardening
- Run T08 unit/integration/scenario tests (including auth scenarios T08-U7, T08-U8, T08-U9).
- Validate latency and reconnect stability for MVP demo.
- Verify auth enforcement for all close code scenarios (4001/4003).
- Verify timezone offset in all event timestamps.
- Update traceability and changelog.
