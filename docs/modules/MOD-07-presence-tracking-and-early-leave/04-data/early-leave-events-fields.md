# Early Leave Events Fields

## Schema Alignment
All fields match `docs/main/database-schema.md` early_leave_events table definition.

## Table
`early_leave_events`

## Module-Relevant Columns
| Column | Type | Constraints | Use in MOD-07 |
|---|---|---|---|
| id | UUID | PK | Event ID |
| attendance_id | UUID | FK → attendance_records.id, NOT NULL | Related attendance context |
| detected_at | TIMESTAMPTZ | NOT NULL | Timestamp when early-leave was flagged |
| last_seen_at | TIMESTAMPTZ | optional | Last known detection before flag |
| consecutive_misses | INTEGER | NOT NULL | Miss count that triggered the flag (≥ EARLY_LEAVE_THRESHOLD) |
| notified | BOOLEAN | DEFAULT false | Whether faculty has been notified (via MOD-08 WebSocket) |
| notified_at | TIMESTAMPTZ | optional | Timestamp of notification delivery |

## Timezone Note
- `detected_at` and `last_seen_at` are TIMESTAMPTZ — stored in UTC, rendered with timezone offset (e.g., `+08:00` for Asia/Manila).
- `notified_at` follows the same pattern.

## Foreign Key Relationships
| FK Column | References | Cascade Behavior |
|---|---|---|
| attendance_id | attendance_records.id | CASCADE on DELETE (user deletion → attendance → early-leave events) |

## Dedup Rule
- One early-leave event per `(attendance_id)` context — prevents duplicate flagging for the same attendance record within a session.

## Indexes
- `idx_early_leave_attendance` on (attendance_id) — for event lookup by attendance record.
- `idx_early_leave_time` on (detected_at) — for time-range queries and alert display.
