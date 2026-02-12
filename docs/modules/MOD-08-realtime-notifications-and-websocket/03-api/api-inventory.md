# API Inventory

## Auth Context
- **WebSocket endpoint (FUN-08-01, FUN-08-05):** Requires Supabase JWT passed as `token` query parameter.
- **System-internal event publishing (FUN-08-02 to FUN-08-04):** No HTTP/WS endpoints — invoked by MOD-06/MOD-07 service layer.

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- WebSocket URL: `ws://localhost:8000/api/v1/ws/{user_id}` (dev), `wss://` (prod)
- Auth: Supabase JWT passed as `token` query parameter during WebSocket handshake

## Endpoint List
| Method | Path | Function ID | Auth Requirement | Caller |
|---|---|---|---|---|
| WS | `/ws/{user_id}` | FUN-08-01, FUN-08-05 | Supabase JWT (query param `token`, all roles) | Mobile clients |

## Event List (Server → Client)
| Event Type | Function ID | Auth | Trigger Source | Direction |
|---|---|---|---|---|
| `attendance_update` | FUN-08-02 | System-internal (no JWT) | Attendance status change (`MOD-06`) | Server → Client |
| `early_leave` | FUN-08-03 | System-internal (no JWT) | Early-leave detection (`MOD-07`) | Server → Client |
| `session_end` | FUN-08-04 | System-internal (no JWT) | Session finalization | Server → Client |

## Event Envelope Format
```json
{
  "type": "event_type_string",
  "data": { ... }
}
```

Note: This is the WebSocket message envelope, not the HTTP response envelope. HTTP error responses (if any REST endpoints are added) use: `{ "success": false, "error": { "code": "", "message": "" } }` (no `details` array — consistent with MOD-01 through MOD-07).

## Heartbeat Notes
- Server sends ping every `WS_HEARTBEAT_INTERVAL` seconds (default: 30).
- Client responds with pong for liveness.
- No pong within `WS_STALE_TIMEOUT` (default: 60s) → connection marked stale and closed.

## Internal Function Flow Context
FUN-08-02, FUN-08-03, and FUN-08-04 are system-internal service functions. They are not exposed as HTTP or WebSocket endpoints. They are invoked by:
- `attendance_service.py` (MOD-06) → FUN-08-02
- `presence_service.py` (MOD-07) → FUN-08-03
- Session finalization flow → FUN-08-04
