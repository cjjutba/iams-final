# MVP Scope

## In Scope
- Session state per schedule/date using configured `TIMEZONE` (default: Asia/Manila).
- Periodic scan evaluation loop at `SCAN_INTERVAL` (default: 60 seconds).
- Miss counter updates per student with deterministic reset/increment.
- Early-leave flag generation at `EARLY_LEAVE_THRESHOLD` (default: 3 consecutive misses).
- Presence score computation: `(scans_detected / total_scans) × 100`.
- Presence logs and early-leave event query APIs with Supabase JWT + faculty/admin role.
- Response envelope: `{ "success": true, "data": {}, "message": "" }` for success; `{ "success": false, "error": { "code": "", "message": "" } }` for errors.

## Out of Scope
- Realtime transport layer implementation (owned by MOD-08).
- Cross-class predictive analytics.
- Advanced anomaly detection beyond configured threshold logic.
- Rate limiting (thesis demonstration).

## MVP Constraints
- Default scan interval: 60 seconds (configurable via `SCAN_INTERVAL` env var).
- Default early-leave threshold: 3 consecutive misses (configurable via `EARLY_LEAVE_THRESHOLD` env var).
- Presence score: `(scans_detected / total_scans) × 100`.
- Session boundaries use `TIMEZONE` env var (default: Asia/Manila, +08:00).
- Presence logs FK-reference `attendance_records.id`; early-leave events FK-reference `attendance_records.id` and `schedules.id`.
- Cascade deletion: user deletion (MOD-02) → attendance_records (MOD-06) → presence_logs + early_leave_events (MOD-07).

## MVP Gate Criteria
- `FUN-07-01` through `FUN-07-06` implemented and tested.
- Threshold/interval configuration works without code changes.
- Early-leave and recovery scenarios match documented behavior.
- Auth enforcement verified: 401 for missing/invalid JWT, 403 for student role on FUN-07-06 endpoints.
- Timezone handling: session boundaries and "today" queries use configured `TIMEZONE` correctly.
- Response envelope format consistent across all endpoint responses.
