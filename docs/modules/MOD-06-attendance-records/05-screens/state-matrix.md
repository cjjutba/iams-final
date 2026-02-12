# Screen State Matrix

| Screen | Loading | Success | Validation Error | Network Error | Auth Error (401) | Permission Error (403) |
|---|---|---|---|---|---|---|
| SCR-011 StudentHomeScreen | show summary skeleton | show today's status cards | N/A | retry + cached view | redirect to login | show error message |
| SCR-013 HistoryScreen | show list skeleton | show sorted records | invalid date filter error | retry + message | redirect to login | show error message |
| SCR-014 DetailScreen | show detail skeleton | show record details | N/A | retry | redirect to login | show error message |
| SCR-019 FacultyHomeScreen | show class summary loading | show class summary | N/A | retry | redirect to login | show error message |
| SCR-021 LiveAttendanceScreen | show session connecting state | show live roster | N/A | reconnect + retry | redirect to login | show error message |
| SCR-024 ManualEntryScreen | disable submit + spinner | show success confirmation | invalid payload/status | retry + preserve form | redirect to login | show role error |

## Required UX Rules
- Preserve manual-entry form data on recoverable errors.
- Keep status color/labels consistent across screens (`present`=green, `late`=yellow, `absent`=red, `early_leave`=orange).
- Display empty states when no records exist.
- Pull-to-refresh on list screens (SCR-013, SCR-021).
- On 401 (expired/invalid JWT): redirect to login screen, clear stored token.
- On 403 (insufficient role): show error message, do NOT redirect to login.
