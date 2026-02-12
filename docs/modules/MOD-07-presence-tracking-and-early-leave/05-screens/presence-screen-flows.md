# Presence Screen Flows

## Faculty Class Detail Flow (SCR-022)
**Auth:** Supabase JWT (faculty role required).
1. Open `SCR-022` — faculty is authenticated via Supabase JWT.
2. Load class-level attendance/presence summary via GET /presence/{attendance_id}/logs.
3. Display session summary cards with presence scores.
4. Drill into student details (navigates to SCR-023).
5. Pull-to-refresh to reload presence data.

## Faculty Student Detail Flow (SCR-023)
**Auth:** Supabase JWT (faculty role required).
1. Open `SCR-023` — navigated from SCR-022 class detail.
2. Fetch presence logs by attendance_id via GET /presence/{attendance_id}/logs.
3. Display scan timeline showing detected/not-detected status per scan.
4. Show miss counter history and presence score.
5. Pull-to-refresh to reload scan timeline.

## Early Leave Alerts Flow (SCR-025)
**Auth:** Supabase JWT (faculty role required).
1. Open `SCR-025` — faculty navigates to early-leave alerts.
2. Fetch early-leave events via GET /presence/early-leaves?schedule_id=uuid&date=YYYY-MM-DD.
3. Display flagged students with miss counts, last-seen times, and flagged-at timestamps.
4. Pull-to-refresh to reload alerts.

## Auth Error Handling
- **401 (Missing/Invalid JWT):** Redirect to login screen. Clear stored tokens.
- **403 (Insufficient Role):** Show error message "You do not have permission to view this data." Do not redirect.
- **Expired JWT:** Same as 401 — redirect to login.
