# Demo Checklist (MOD-06)

## Core Functionality
- [ ] Recognition event marks attendance without duplicate row creation.
- [ ] Today's attendance endpoint shows records and summary with all 4 status counts.
- [ ] Student can view own attendance history with date range filters.
- [ ] Faculty can query class attendance history for assigned schedules.
- [ ] Faculty manual entry creates/updates record with required remarks.
- [ ] Live attendance endpoint returns active session roster with presence data.
- [ ] Inactive session returns `{ "session_active": false }` with appropriate message.

## Auth Verification
- [ ] All endpoints reject requests without JWT (401).
- [ ] Faculty-only endpoints reject student JWT (403).
- [ ] GET /attendance/me returns role-scoped data (student sees own, faculty sees own classes).
- [ ] Expired JWT returns 401 on all endpoints.

## Access Control
- [ ] Student cannot call POST /attendance/manual (403).
- [ ] Student cannot call GET /attendance/today (403).
- [ ] Student cannot call GET /attendance/live/{id} (403).
- [ ] Faculty cannot query unassigned schedule history (403).
- [ ] Admin has unrestricted access to all attendance data.

## Data Integrity
- [ ] Duplicate attendance marking for same student/schedule/date is prevented.
- [ ] Manual entry stores audit trail (remarks, updated_by, updated_at).
- [ ] Status values are restricted to: present, late, absent, early_leave.
- [ ] Invalid date range (start > end) returns 422.

## Screen Integration
- [ ] Student home screen (SCR-011) shows today's attendance status.
- [ ] Student history screen (SCR-013) shows filtered records with pull-to-refresh.
- [ ] Faculty home screen (SCR-019) shows class attendance overview.
- [ ] Faculty live screen (SCR-021) shows real-time roster with presence indicators.
- [ ] Faculty manual entry screen (SCR-024) submits successfully with remarks.
- [ ] UI screens show consistent status labels and colors.

## Timezone
- [ ] "Today" queries return correct results for Asia/Manila timezone.
- [ ] Date range filters interpret dates in configured timezone.
- [ ] Timestamps in responses include timezone offset (+08:00).
