# Demo Checklist (MOD-07)

## Core Functionality
- [ ] Session starts with correct schedule/date context using configured `TIMEZONE`.
- [ ] Scan loop updates presence logs at configured `SCAN_INTERVAL` (default: 60s).
- [ ] Miss counters increment and reset correctly (deterministic behavior).
- [ ] Early-leave event appears when `EARLY_LEAVE_THRESHOLD` (default: 3) is reached.
- [ ] Brief absence recovery does not trigger false early-leave (counter resets on detection).
- [ ] Presence score updates consistently with scan totals.
- [ ] Duplicate early-leave events are prevented for same attendance context.

## Auth Verification
- [ ] GET /presence/{attendance_id}/logs rejects requests without JWT (401).
- [ ] GET /presence/early-leaves rejects requests without JWT (401).
- [ ] GET /presence/{attendance_id}/logs rejects student JWT (403).
- [ ] GET /presence/early-leaves rejects student JWT (403).
- [ ] Expired JWT returns 401 on all endpoints.

## Access Control
- [ ] Faculty can view presence logs for their assigned schedules.
- [ ] Admin can view presence logs for any schedule.
- [ ] Student cannot access any MOD-07 endpoint (403).

## Data Integrity
- [ ] Presence logs reference valid attendance records (FK constraint).
- [ ] Early-leave events reference valid attendance records.
- [ ] Event timestamps are monotonic within session context.
- [ ] User deletion cascades to presence data via attendance records.

## Screen Integration
- [ ] Presence logs endpoint returns expected timeline for SCR-023.
- [ ] Early-leave endpoint returns expected flagged students for SCR-025.
- [ ] Faculty class detail shows session summary for SCR-022.
- [ ] Pull-to-refresh works on all presence screens.

## Timezone
- [ ] Session boundaries use configured `TIMEZONE` env var (default: Asia/Manila).
- [ ] "Today" queries return correct results for configured timezone.
- [ ] Timestamps in API responses include timezone offset (e.g., `+08:00`).
