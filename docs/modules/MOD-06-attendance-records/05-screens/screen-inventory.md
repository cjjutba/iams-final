# Screen Inventory (MOD-06)

## Included Screens
| Screen ID | Screen Name | Role | Auth | Attendance Module Usage |
|---|---|---|---|---|
| SCR-011 | StudentHomeScreen | Student | Supabase JWT (student) | today's attendance overview |
| SCR-013 | StudentAttendanceHistoryScreen | Student | Supabase JWT (student) | attendance history list with date filters |
| SCR-014 | StudentAttendanceDetailScreen | Student | Supabase JWT (student) | day/detail view of single record |
| SCR-019 | FacultyHomeScreen | Faculty | Supabase JWT (faculty) | class attendance overview |
| SCR-021 | FacultyLiveAttendanceScreen | Faculty | Supabase JWT (faculty) | live class monitoring with presence state |
| SCR-024 | FacultyManualEntryScreen | Faculty | Supabase JWT (faculty) | manual attendance entry/override |

## Screen-to-Function Mapping
- SCR-011 → FUN-06-02 (today's summary view)
- SCR-013 → FUN-06-03 (student personal history)
- SCR-014 → FUN-06-03/FUN-06-04 (detail view of specific record)
- SCR-019 → FUN-06-02 (faculty class overview)
- SCR-021 → FUN-06-06 (live attendance session)
- SCR-024 → FUN-06-05 (manual attendance entry)

## API Calls per Screen
| Screen | API Call | Auth |
|---|---|---|
| SCR-011 | GET /attendance/today?schedule_id=... | Supabase JWT |
| SCR-013 | GET /attendance/me?start_date=...&end_date=... | Supabase JWT |
| SCR-014 | GET /attendance/me (single record detail) | Supabase JWT |
| SCR-019 | GET /attendance/today?schedule_id=... | Supabase JWT |
| SCR-021 | GET /attendance/live/{schedule_id} | Supabase JWT |
| SCR-024 | POST /attendance/manual | Supabase JWT |
