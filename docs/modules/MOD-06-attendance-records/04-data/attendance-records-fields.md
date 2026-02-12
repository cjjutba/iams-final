# Attendance Records Fields

## Table
`attendance_records`

## Module-Relevant Columns
| Column | Type | Constraints | Use in MOD-06 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | record identifier |
| student_id | UUID | FK → users.id, NOT NULL | student linkage |
| schedule_id | UUID | FK → schedules.id, NOT NULL | class linkage |
| date | DATE | NOT NULL | attendance day (in configured timezone) |
| status | VARCHAR(20) | NOT NULL | one of: present, late, absent, early_leave |
| check_in_time | TIMESTAMPTZ | optional | first detection timestamp |
| check_out_time | TIMESTAMPTZ | optional | last detection timestamp |
| presence_score | DECIMAL(5,2) | optional | computed by MOD-07 presence tracking |
| remarks | TEXT | optional | manual override notes / audit trail |
| updated_by | UUID | FK → users.id, optional | user ID of faculty/admin who performed manual override |
| created_at | TIMESTAMPTZ | DEFAULT now() | record creation timestamp |
| updated_at | TIMESTAMPTZ | DEFAULT now() | last update timestamp |

## Constraints and Indexes
- UNIQUE `(student_id, schedule_id, date)` — prevents duplicate attendance rows
- `idx_attendance_student_date` — optimizes student history queries (FUN-06-03)
- `idx_attendance_schedule_date` — optimizes schedule-scoped queries (FUN-06-02, FUN-06-04)
- `idx_attendance_status` — optimizes status-based filtering

## Timezone Note
- `check_in_time` and `check_out_time` are stored as TIMESTAMPTZ (with timezone info).
- `date` column represents the attendance date in the configured timezone (`TIMEZONE` env var, default: Asia/Manila).
- "Today" queries derive the current date from the configured timezone, not UTC.

## Foreign Key Relationships
- `student_id` → `users.id` (CASCADE on delete — student removal deletes attendance records)
- `schedule_id` → `schedules.id` (no cascade — schedule deactivation preserves historical attendance)
- `updated_by` → `users.id` (optional — only set for manual overrides)
