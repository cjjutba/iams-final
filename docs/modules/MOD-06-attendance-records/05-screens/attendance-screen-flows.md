# Attendance Screen Flows

## Student Attendance Flow
1. Open `SCR-011` (StudentHomeScreen) for today's status snapshot.
   - Auth: Supabase JWT required. Redirects to login if 401.
   - API: `GET /attendance/today?schedule_id=...`
2. Open `SCR-013` (StudentAttendanceHistoryScreen) for historical records list.
   - Auth: Supabase JWT required. Shows own records only (JWT sub scoped).
   - API: `GET /attendance/me?start_date=...&end_date=...`
   - Pull-to-refresh supported.
3. Open `SCR-014` (StudentAttendanceDetailScreen) for detailed record view.
   - Auth: Supabase JWT required.

## Faculty Attendance Flow
1. Open `SCR-019` (FacultyHomeScreen) for class overview.
   - Auth: Supabase JWT required. Faculty role.
   - API: `GET /attendance/today?schedule_id=...`
2. Open `SCR-021` (FacultyLiveAttendanceScreen) for live attendance monitoring.
   - Auth: Supabase JWT required. Faculty role.
   - API: `GET /attendance/live/{schedule_id}`
   - Pull-to-refresh supported. Auto-refresh on scan interval.
3. Use `SCR-024` (FacultyManualEntryScreen) to submit manual attendance entries.
   - Auth: Supabase JWT required. Faculty role.
   - API: `POST /attendance/manual`

## Data Fetch Sequence
- Today's view: `GET /attendance/today?schedule_id=...`
- Student history: `GET /attendance/me?start_date=...&end_date=...`
- Class history: `GET /attendance?schedule_id=...&start_date=...&end_date=...`
- Manual entry: `POST /attendance/manual`
- Live monitoring: `GET /attendance/live/{schedule_id}`

## Auth Error Handling
- **401 (Unauthorized):** Redirect to login screen. Clear stored JWT.
- **403 (Forbidden):** Display role-based error message (e.g., "You don't have permission to access this resource"). Do NOT redirect to login.
