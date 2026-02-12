# UI State Matrix

| State | SCR-021 FacultyLiveAttendance | SCR-025 FacultyEarlyLeaveAlerts | SCR-029 FacultyNotifications | SCR-018 StudentNotifications |
|---|---|---|---|---|
| Initial loading | Show live-session skeleton | Show alerts skeleton | Show feed skeleton | Show feed skeleton |
| Connected idle | Live view active, waiting events | Empty alerts state | Empty/feed ready state | Empty/feed ready state |
| attendance_update received | Update roster status row | — | Add feed item | Add feed item (if routed) |
| early_leave received | Show alert indicator and list update | Add alert card with student details | Add alert feed item | — (faculty-targeted) |
| session_end received | Show summary and close active state | — | Add summary event | Add summary event |
| Disconnected | Show reconnecting badge | Show reconnecting badge | Show reconnecting badge | Show reconnecting badge |
| Reconnected | Refresh indicator and continue stream | Continue stream | Continue stream | Continue stream |
| Auth Error (4001) | Redirect to login, show "Session expired" | Redirect to login | Redirect to login | Redirect to login |
| Permission Error (4003) | Show error message (connection forbidden) | Show error message | Show error message | Show error message |
| Error | Show non-blocking realtime error | Show non-blocking error | Show non-blocking realtime error | Show non-blocking realtime error |

## UX Rules
1. **Pull-to-refresh:** Available on SCR-021, SCR-029, SCR-018. Re-fetches current state via REST API; does not affect WebSocket connection.
2. **Reconnecting badge:** Non-blocking indicator shown during reconnect attempts. Auto-clears when connection restored.
3. **Auth error (4001):** Clear stored JWT, redirect to login screen, show toast "Session expired."
4. **Permission error (4003):** Show inline error message. Do not redirect (likely client-side bug).
5. **Exponential backoff:** Reconnect attempts use `WS_RECONNECT_BASE_DELAY_MS` (1s) to `WS_RECONNECT_MAX_DELAY_MS` (10s).
6. **No app restart required:** Reconnect should resume event stream without requiring user to close and reopen app.
7. **Timestamp display:** All event timestamps displayed using timezone offset from event payload (+08:00).
