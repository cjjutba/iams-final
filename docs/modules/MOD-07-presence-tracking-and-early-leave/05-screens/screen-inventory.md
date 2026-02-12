# Screen Inventory (MOD-07)

## Included Screens
| Screen ID | Screen Name | Role | Auth | Presence Module Usage |
|---|---|---|---|---|
| SCR-022 | FacultyClassDetailScreen | Faculty | Supabase JWT (faculty) | Class presence summary/details |
| SCR-023 | FacultyStudentDetailScreen | Faculty | Supabase JWT (faculty) | Per-student presence logs and status |
| SCR-025 | FacultyEarlyLeaveAlertsScreen | Faculty | Supabase JWT (faculty) | Early-leave events list |

## Screen-to-Function Mapping
| Screen | Function | API Call |
|---|---|---|
| SCR-022 | FUN-07-06 | GET /presence/{attendance_id}/logs (session context) |
| SCR-023 | FUN-07-06 | GET /presence/{attendance_id}/logs (student detail) |
| SCR-025 | FUN-07-06 | GET /presence/early-leaves?schedule_id=uuid&date=YYYY-MM-DD |

## API Calls per Screen
| Screen | Endpoint | Auth | Purpose |
|---|---|---|---|
| SCR-022 | GET /presence/{attendance_id}/logs | Supabase JWT (faculty) | Load class-level presence summary |
| SCR-023 | GET /presence/{attendance_id}/logs | Supabase JWT (faculty) | Load per-student scan timeline |
| SCR-025 | GET /presence/early-leaves | Supabase JWT (faculty) | Load early-leave flagged students |
