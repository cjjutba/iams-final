# Data Model Inventory

## Primary Module Data (Ephemeral)
| Data | Storage | Ownership | Description |
|---|---|---|---|
| Connection map | In-memory (dict) | MOD-08 | Active WebSocket connections keyed by `user_id` |
| Heartbeat/liveness metadata | In-memory | MOD-08 | `last_seen_at`, `is_alive` per connection |
| Message delivery logs | In-memory or file (optional) | MOD-08 | Event delivery outcomes for debugging |

## Consumed Domain Data (Read/Input)
| Table | Source Module | Purpose |
|---|---|---|
| `attendance_records` | MOD-06 | Source context for `attendance_update` events |
| `early_leave_events` | MOD-07 | Source context for `early_leave` events |
| `schedules` | MOD-05 | Session metadata, recipient resolution |
| `enrollments` | MOD-05 | Resolve enrolled students for fanout |
| `users` | MOD-02 | Recipient identity context |

## Backend File Paths
- `backend/app/services/notification_service.py` — connection map, event publishing
- `backend/app/routers/websocket.py` — WebSocket endpoint

## Cross-Module Data Flow
| Source | Event | Data Consumed | Target |
|---|---|---|---|
| MOD-06 (attendance_service) | `attendance_update` | student_id, schedule_id, status, timestamp | Connected clients |
| MOD-07 (presence_service) | `early_leave` | student_id, schedule_id, detected_at | Connected faculty |
| Session finalization | `session_end` | schedule_id, summary counts | Connected clients |
| MOD-02 (user deletion) | User removed | user_id | Close WS connection, remove from map |

## MOD-02 User Deletion Impact
When a user is deleted (MOD-02), MOD-08 should:
1. Close any active WebSocket connection for the deleted `user_id`.
2. Remove entry from connection map.
3. No cascade concern since MOD-08 has no relational tables.

## Persistence Note
- Module 8 does not require new relational tables in MVP.
- Connection state is ephemeral (lost on server restart).
- Delivery logging is optional, controlled by `WS_ENABLE_DELIVERY_LOGS` (default: disabled).
- If enabled, delivery logs use in-memory ring buffer or file stream (not database).

## Data Lifecycle
1. **Connect:** Socket registered in connection map with `connected_at` timestamp.
2. **Active:** Events received and forwarded; heartbeat tracked via `last_seen_at`.
3. **Stale:** Heartbeat timeout or send failure marks entry as stale.
4. **Cleanup:** Stale entry removed from map, socket closed.
5. **Server Restart:** All connection state lost (clients must reconnect).
