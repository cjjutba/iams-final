# Endpoint Contract: WS /ws/{user_id}

## Purpose
Open and maintain authenticated realtime channel for user-scoped event delivery.

## Route
- Method: `WS`
- Path: `/ws/{user_id}`
- Full URL: `ws://localhost:8000/api/v1/ws/{user_id}?token=<jwt>` (dev)
- Production: `wss://` over HTTPS

## Path Params
| Name | Type | Required | Notes |
|---|---|---|---|
| `user_id` | UUID | Yes | Must match JWT `sub` claim |

## Query Params
| Name | Type | Required | Notes |
|---|---|---|---|
| `token` | string | Yes | Supabase JWT for authentication |

## Auth Requirement
- **Auth Method:** Supabase JWT passed as `token` query parameter.
- **JWT Claims Used:** `sub` (user ID), `exp` (expiration), `role` (user role).
- **Identity Check:** JWT `sub` must match path `user_id`.
- **Roles Allowed:** All authenticated roles (student, faculty, admin).
- **Close code 4001:** Missing, invalid, or expired JWT.
- **Close code 4003:** `user_id` does not match JWT `sub`.

## Connection Lifecycle
1. Client opens socket to `/ws/{user_id}?token=<jwt>`.
2. Server extracts JWT from `token` query parameter.
3. Server validates JWT signature and expiration using `JWT_SECRET_KEY`.
4. Server compares JWT `sub` with path `user_id`.
5. If mismatch → close with code 4003 (Forbidden).
6. If invalid/expired → close with code 4001 (Unauthorized).
7. Server evicts any stale entry for same `user_id`.
8. Server registers connection in active map with `connected_at` timestamp.
9. Server sends realtime events while connected.
10. On disconnect/error/heartbeat timeout, server removes mapping.

## Message Envelope
```json
{
  "type": "attendance_update",
  "data": {
    "student_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "schedule_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "status": "present",
    "timestamp": "2026-02-12T08:05:00+08:00"
  }
}
```

## Timezone Note
All event timestamps use ISO-8601 format with timezone offset based on `TIMEZONE` env var (default: Asia/Manila, +08:00).

## Close/Error Cases
| Condition | Close Code | Description |
|---|---|---|
| Missing/invalid/expired JWT | 4001 | Unauthorized — connection rejected |
| `user_id` mismatch with JWT `sub` | 4003 | Forbidden — identity mismatch |
| Heartbeat timeout (no pong) | 1000 | Normal close after stale detection |
| Send failure | 1011 | Unexpected condition — logged and cleaned up |
| Server error | 1011 | Internal error — close and log |

## Notes
- Reconnect follows same auth flow (FUN-08-05 delegates to FUN-08-01).
- Stale entries evicted before new registration (idempotent reconnect).
- Heartbeat ping sent every `WS_HEARTBEAT_INTERVAL` seconds (default: 30).
