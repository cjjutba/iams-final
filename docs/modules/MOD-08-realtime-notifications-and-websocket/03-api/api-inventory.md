# API Inventory

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- WebSocket URL: `ws://localhost:8000/api/v1/ws/{user_id}`
- Auth: same token model as protected HTTP routes

## Endpoint List
| Method | Path | Function ID | Caller | Auth Required |
|---|---|---|---|---|
| WS | `/ws/{user_id}` | FUN-08-01, FUN-08-05 | mobile clients | Yes |

## Event List
| Event Type | Function ID | Direction | Trigger Source |
|---|---|---|---|
| `attendance_update` | FUN-08-02 | Server -> Client | Attendance state change (`MOD-06`) |
| `early_leave` | FUN-08-03 | Server -> Client | Early-leave detection (`MOD-07`) |
| `session_end` | FUN-08-04 | Server -> Client | Session finalization |

## Heartbeat Notes
- Technical spec indicates heartbeat every 30 seconds.
- Ping/pong can be used by both client and server for liveness.
