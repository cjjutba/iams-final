# Goal and Objectives

## Module Goal
Continuously track in-session student presence and detect early-leave behavior with configurable thresholds and reliable logs.

## Auth Context
- FUN-07-01 to FUN-07-05 are **system-internal** service functions (no HTTP endpoints, no JWT).
- FUN-07-06 exposes **user-facing query endpoints** requiring Supabase JWT with faculty/admin role.
- 401 for missing/invalid JWT, 403 for insufficient role on FUN-07-06 endpoints.

## Primary Objectives
1. Start and maintain schedule-scoped session state tied to `schedules.id` and date context.
2. Execute periodic scan logic at `SCAN_INTERVAL` (default: 60 seconds).
3. Maintain per-student miss counters and detection state with deterministic reset/increment logic.
4. Flag early leave when `EARLY_LEAVE_THRESHOLD` (default: 3) consecutive misses is reached.
5. Compute presence score: `(scans_detected / total_scans) × 100`.
6. Expose presence logs and early-leave events via authenticated API (Supabase JWT, faculty/admin).

## Success Outcomes
- Session state is tied to schedule/date context consistently using configured `TIMEZONE` (default: Asia/Manila).
- Miss-counter logic is deterministic and test-covered.
- Early-leave events are generated only when threshold conditions are met.
- Presence logs are queryable and align with attendance records (FK: `attendance_records.id`).
- All query endpoints enforce Supabase JWT + role-based access.

## Non-Goals (for MOD-07 MVP)
- Computer-vision face recognition model training (owned by MOD-03).
- Realtime event transport implementation (owned by MOD-08).
- Full analytics dashboard.
- Rate limiting (thesis demonstration).

## Stakeholders
- **Faculty:** Consume early-leave alerts and detailed presence data via SCR-022, SCR-023, SCR-025.
- **Students:** Indirectly affected via attendance status outcomes (present → early_leave transition).
- **MOD-06:** Provides attendance records that MOD-07 presence logs reference.
- **MOD-08:** Consumes early-leave events for WebSocket broadcast to mobile clients.
- **MOD-03/MOD-04:** Recognition pipeline triggers scan results that feed MOD-07 presence evaluation.
