# Message Delivery Log Model (Optional)

## Purpose
Track event delivery outcomes for debugging and thesis validation.

## Status
- **Default:** Disabled (`WS_ENABLE_DELIVERY_LOGS=false`).
- **When enabled:** Logs delivery attempts for observability.
- **Not required for MVP** — enable only for debugging or demo validation.

## Suggested Fields
| Field | Type | Description |
|---|---|---|
| `id` | UUID/string | Log record ID |
| `event_type` | string | Event name (`attendance_update`, `early_leave`, `session_end`) |
| `function_id` | string | `FUN-08-*` traceability |
| `target_user_id` | UUID | Recipient user |
| `delivered_at` | ISO-8601 datetime | Delivery attempt time with timezone offset |
| `result` | string | `success` or `failure` |
| `error` | string | Error detail if failed (null on success) |
| `schedule_id` | UUID | Schedule context (if available) |

## Storage Options
| Option | Use Case | Notes |
|---|---|---|
| In-memory ring buffer | Development/testing | Lost on restart, bounded size |
| File log stream | Debugging | Append-only, requires log rotation |
| Database table | Future (post-MVP) | Not required for MVP |

## Retention Rule
If persisted, keep only bounded retention for MVP (7 to 30 days).

## Configuration
- Controlled by `WS_ENABLE_DELIVERY_LOGS` env var (default: `false`).
- When disabled, no delivery logging occurs (zero overhead).
- When enabled, logs are written to in-memory ring buffer or file (implementation choice).
