# UI State Matrix

| State | SCR-021 FacultyLiveAttendance | SCR-029 FacultyNotifications | SCR-018 StudentNotifications |
|---|---|---|---|
| Initial loading | Show live-session skeleton | Show feed skeleton | Show feed skeleton |
| Connected idle | Live view active, waiting events | Empty/feed ready state | Empty/feed ready state |
| attendance_update received | Update roster status row | Add feed item (if routed) | Add feed item (if routed) |
| early_leave received | Show alert indicator and list update | Add alert feed item | Add item only if routing policy includes student |
| session_end received | Show summary and close active state | Add summary event | Add summary event |
| Disconnected | Show reconnecting badge | Show reconnecting badge | Show reconnecting badge |
| Reconnected | Refresh indicator and continue stream | Continue stream | Continue stream |
| Error | Show non-blocking realtime error | Show non-blocking realtime error | Show non-blocking realtime error |
