# Screen State Matrix

| Screen | Loading | Success | Validation/Error | Network Error |
|---|---|---|---|---|
| SCR-022 FacultyClassDetailScreen | load class presence summary | show session summary/cards | invalid class filter/date | retry + message |
| SCR-023 FacultyStudentDetailScreen | load scan timeline | show log entries | invalid attendance_id | retry + message |
| SCR-025 FacultyEarlyLeaveAlertsScreen | load alerts list | show flagged students | invalid date filter | retry + message |

## Required UX Rules
- Show explicit empty states when no flags/logs exist.
- Keep scan order chronological.
- Surface threshold context when showing early-leave events.
