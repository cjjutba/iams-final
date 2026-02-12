# Presence Logs Fields

## Schema Alignment
All fields match `docs/main/database-schema.md` presence_logs table definition.

## Table
`presence_logs`

## Module-Relevant Columns
| Column | Type | Constraints | Use in MOD-07 |
|---|---|---|---|
| id | BIGSERIAL | PK | Log row ID (auto-increment) |
| attendance_id | UUID | FK → attendance_records.id, NOT NULL | Parent attendance record |
| scan_number | INTEGER | NOT NULL | Scan sequence index within session |
| scan_time | TIMESTAMPTZ | NOT NULL | Scan timestamp (includes timezone offset) |
| detected | BOOLEAN | NOT NULL | Detected/not-detected result for this scan |
| confidence | DECIMAL(5,4) | optional | Match confidence (0-1), from recognition pipeline |

## Timezone Note
- `scan_time` is TIMESTAMPTZ — stored in UTC, rendered with timezone offset (e.g., `+08:00` for Asia/Manila).
- Session date context uses configured `TIMEZONE` env var.

## Foreign Key Relationships
| FK Column | References | Cascade Behavior |
|---|---|---|
| attendance_id | attendance_records.id | CASCADE on DELETE (user deletion → attendance → presence logs) |

## Indexes
- `idx_presence_attendance` on (attendance_id) — for log lookup by attendance record.
- `idx_presence_time` on (scan_time) — for time-range queries.
