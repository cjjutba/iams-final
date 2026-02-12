# Implementation Plan (MOD-07)

## Phase 0: Foundations
- Verify MOD-06 attendance records implementation is complete and stable.
- Verify schedule/enrollment data available from MOD-05.
- Confirm Supabase JWT auth middleware is in place (shared with MOD-01/02/05/06).
- Verify SQLAlchemy `PresenceLog` and `EarlyLeaveEvent` models exist and match `database-schema.md`.
- Configure `TIMEZONE`, `SCAN_INTERVAL`, `EARLY_LEAVE_THRESHOLD` env vars.
- Set up presence router skeleton at `/api/v1/presence`.

## Phase 1: Session and Scan Engine
- Implement session initialization and lifecycle controls (FUN-07-01).
- Implement periodic scan processing loop at `SCAN_INTERVAL` (FUN-07-02).
- Use configured `TIMEZONE` for session boundaries.

## Phase 2: Counter and Event Logic
- Implement miss counter transitions with deterministic reset/increment (FUN-07-03).
- Implement threshold-based early-leave event creation (FUN-07-04).
- Add dedup: one early-leave event per `(attendance_id)` context.
- Update attendance status to `early_leave` via MOD-06 integration.
- Emit event for MOD-08 WebSocket broadcast.

## Phase 3: Score and Persistence
- Implement presence score computation: `(scans_detected / total_scans) × 100` (FUN-07-05).
- Handle zero-scan edge case (score = 0).
- Persist logs/events with attendance linkage (FK → `attendance_records.id`).

## Phase 4: API Exposure
- Implement logs and early-leave query endpoints (FUN-07-06).
- Enforce Supabase JWT + faculty/admin role check.
- Return 401 for missing/invalid JWT, 403 for insufficient role.
- Use response envelope: `{ "success": true, "data": {}, "message": "" }`.

## Phase 5: Mobile Integration
- Wire faculty presence screens (SCR-022, SCR-023, SCR-025) to GET /presence/* endpoints.
- Add loading/empty/error states, pull-to-refresh.
- Handle 401 (redirect to login) and 403 (show error message).

## Phase 6: Validation
- Run unit/integration/scenario tests (including auth and timezone scenarios).
- Validate acceptance criteria and update traceability.
- Verify timezone configuration and session boundary consistency.
- Verify auth enforcement for all role combinations (401/403).
