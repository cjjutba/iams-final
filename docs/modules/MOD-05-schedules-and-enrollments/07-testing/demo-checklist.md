# Demo Checklist (MOD-05)

## Core Functionality
- [ ] Schedule list endpoint returns records filtered by day (e.g., day=1 returns Monday schedules).
- [ ] Schedule detail endpoint returns full schedule with faculty name and room.
- [ ] Admin can create schedule with valid payload (201 response).
- [ ] Non-admin schedule creation is blocked (403 response).
- [ ] Student `GET /schedules/me` returns only enrolled schedules.
- [ ] Faculty `GET /schedules/me` returns only teaching schedules.
- [ ] Roster endpoint returns enrolled students for schedule.

## Auth Verification
- [ ] All endpoints return 401 when JWT is missing.
- [ ] All endpoints return 401 when JWT is invalid/expired.
- [ ] POST /schedules returns 403 for faculty caller.
- [ ] POST /schedules returns 403 for student caller.

## Access Control
- [ ] Faculty can view roster for their own schedules.
- [ ] Faculty cannot view roster for other faculty's schedules (403).
- [ ] Enrolled student can view roster for their schedule.
- [ ] Non-enrolled student cannot view roster (403).

## Data Integrity
- [ ] Schedule sorting is consistent (day_of_week ASC, start_time ASC).
- [ ] Only is_active=true schedules are returned in list queries.
- [ ] Enrollment uniqueness constraint prevents duplicate enrollments.
- [ ] Student deletion cascades to enrollment removal.

## Screen Integration
- [ ] Student schedule screen renders enrolled schedules grouped by day.
- [ ] Faculty schedule screen renders teaching schedules grouped by day.
- [ ] Pull-to-refresh works on both schedule screens.
- [ ] Empty state shown when no schedules assigned.

## Timezone
- [ ] Time comparisons use configured timezone (Asia/Manila for JRMSU pilot).
