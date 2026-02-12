# Endpoint Contract: Student Notifications

## Scope
Realtime event subscription used by student notifications screen.

## Endpoint
| Endpoint | Auth | Purpose |
|---|---|---|
| `WS /ws/{user_id}?token=<jwt>` | Post-auth (JWT via query param) | Student notification stream |

**Note**: WebSocket uses JWT via `token` query parameter (not Authorization header) due to WS handshake limitations.

## Connection URL
```
ws://localhost:8000/api/v1/ws/{user_id}?token=<jwt>
```
Production: `wss://<host>/api/v1/ws/{user_id}?token=<jwt>`

## Event Envelope Format
```json
{
  "type": "attendance_update",
  "data": {
    "student_id": "uuid",
    "schedule_id": "uuid",
    "status": "present",
    "timestamp": "2026-02-12T07:02:15+08:00"
  }
}
```
**Note**: WebSocket event envelope `{ "type", "data" }` is distinct from HTTP response envelope `{ "success", "data", "message" }`.

## Event Types (Student-Relevant)
| Event Type | Description | Data Fields |
|---|---|---|
| `attendance_update` | Attendance status change | `student_id`, `schedule_id`, `status`, `timestamp` |
| `session_end` | Class session ended | `schedule_id`, `summary`, `timestamp` |
| `early_leave` | Early leave detection (optional for students) | `student_id`, `schedule_id`, `detected_at` |

## Close Codes
| Code | Meaning | Client Action |
|---|---|---|
| 4001 | Unauthorized (invalid/expired JWT) | Redirect to login screen |
| 4003 | Forbidden (user_id mismatch with JWT) | Show permission error message |
| 1000 | Normal close | No action needed |
| 1011 | Server error | Retry with exponential backoff |

## Timezone Note
All timestamps in event data use ISO-8601 with +08:00 offset (Asia/Manila).

## Client Rules
1. Connect only after auth state is ready (JWT available in SecureStore).
2. Display connection status when disconnected/reconnecting.
3. Parse event envelope safely and ignore unknown types (no crash).
4. Resume stream on reconnect without app restart.
5. On close code 4001: redirect to login screen.
6. On close code 4003: show permission error message.
7. Use exponential backoff for reconnect attempts.

## Screen
- `SCR-018` StudentNotificationsScreen
