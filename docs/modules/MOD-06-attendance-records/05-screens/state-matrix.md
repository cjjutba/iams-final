# Screen State Matrix

| Screen | Loading | Success | Validation Error | Network Error |
|---|---|---|---|---|
| SCR-011 StudentHomeScreen | show summary skeleton | show today's status cards | N/A | retry + cached view |
| SCR-013 HistoryScreen | show list skeleton | show sorted records | invalid date filter error | retry + message |
| SCR-014 DetailScreen | show detail skeleton | show record details | N/A | retry |
| SCR-019 FacultyHomeScreen | show class summary loading | show class summary | N/A | retry |
| SCR-021 LiveAttendanceScreen | show session connecting state | show live roster | N/A | reconnect + retry |
| SCR-024 ManualEntryScreen | disable submit + spinner | show success confirmation | invalid payload/status | retry + preserve form |

## Required UX Rules
- Preserve manual-entry form data on recoverable errors.
- Keep status color/labels consistent across screens.
- Display empty states when no records exist.
