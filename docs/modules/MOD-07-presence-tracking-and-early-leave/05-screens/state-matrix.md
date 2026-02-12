# Screen State Matrix

| Screen | Loading | Success | Validation/Error | Network Error | Auth Error (401) | Permission Error (403) |
|---|---|---|---|---|---|---|
| SCR-022 FacultyClassDetailScreen | Load class presence summary | Show session summary/cards | Invalid class filter/date | Retry + message | Redirect to login | Show error message |
| SCR-023 FacultyStudentDetailScreen | Load scan timeline | Show log entries | Invalid attendance_id | Retry + message | Redirect to login | Show error message |
| SCR-025 FacultyEarlyLeaveAlertsScreen | Load alerts list | Show flagged students | Invalid date filter | Retry + message | Redirect to login | Show error message |

## Required UX Rules
- Show explicit empty states when no flags/logs exist ("No presence logs for this session" / "No early-leave events").
- Keep scan order chronological (sorted by scan_number ascending).
- Surface threshold context when showing early-leave events (e.g., "Flagged after 3 consecutive missed scans").
- Support pull-to-refresh on all screens.
- Handle 401 by redirecting to login and clearing stored tokens.
- Handle 403 by showing inline error message (do not redirect).
- Timestamps display with timezone offset (e.g., `08:05 AM +08:00`).
