# Endpoint Contract: Faculty Notifications

## Scope
Realtime event stream used by faculty notification and live-class screens.

## Endpoint
- `WS /ws/{user_id}?token=<jwt>`
- **Auth:** Post-auth — JWT passed via `token` query parameter (not Authorization header).

## Connection URL
- Development: `ws://localhost:8000/api/v1/ws/{user_id}?token=<jwt>`
- Production: `wss://<domain>/api/v1/ws/{user_id}?token=<jwt>`

## Event Envelope Format
WebSocket messages use a different envelope from HTTP responses:
```json
{ "type": "event_type", "data": { ... } }
```

> This is NOT the same as the HTTP response envelope. Do not parse WebSocket messages as HTTP envelopes.

## Event Types
| Event Type | Data Fields | Used By |
|---|---|---|
| `attendance_update` | `student_id`, `student_name`, `status`, `schedule_id`, `timestamp` | FUN-10-03 (live roster) |
| `early_leave` | `student_id`, `student_name`, `schedule_id`, `detected_at` | FUN-10-05 (alert feed) |
| `session_end` | `schedule_id`, `summary` | FUN-10-05 (class summary) |

## Close Codes
| Code | Meaning | Client Action |
|---|---|---|
| 4001 | Unauthorized (invalid/expired JWT) | Redirect to login screen |
| 4003 | Forbidden (valid JWT but insufficient role) | Show error message |
| 1000 | Normal closure | No action needed |
| 1011 | Server error | Reconnect with exponential backoff |

## Client Rules
1. Connect only after faculty auth/session readiness.
2. Render reconnecting state during network loss.
3. Resume stream without app restart.
4. Parse event envelope safely and ignore unknown types.
5. On close code 4001: clear session and redirect to login.
6. On close code 4003: show forbidden error message.
7. On 1011 or network loss: reconnect with exponential backoff.

## Screens
- `SCR-021` FacultyLiveAttendanceScreen
- `SCR-029` FacultyNotificationsScreen
