# Early Leave Events Fields

## Table
`early_leave_events`

## Module-Relevant Columns
| Column | Type | Constraints | Use in MOD-07 |
|---|---|---|---|
| id | UUID | PK | event id |
| attendance_id | UUID | FK attendance_records | related attendance context |
| detected_at | TIMESTAMPTZ | NOT NULL | flag timestamp |
| last_seen_at | TIMESTAMPTZ | optional | last known detection |
| consecutive_misses | INTEGER | NOT NULL | miss threshold count |
| notified | BOOLEAN | DEFAULT false | notification status |
| notified_at | TIMESTAMPTZ | optional | notification timestamp |

## Indexes
- `idx_early_leave_attendance`
- `idx_early_leave_time`
