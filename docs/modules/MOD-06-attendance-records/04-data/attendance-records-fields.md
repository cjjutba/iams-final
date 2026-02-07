# Attendance Records Fields

## Table
`attendance_records`

## Module-Relevant Columns
| Column | Type | Constraints | Use in MOD-06 |
|---|---|---|---|
| id | UUID | PK | record id |
| student_id | UUID | FK users | student linkage |
| schedule_id | UUID | FK schedules | class linkage |
| date | DATE | NOT NULL | attendance day |
| status | VARCHAR(20) | NOT NULL | present/late/absent/early_leave |
| check_in_time | TIMESTAMPTZ | optional | first detection |
| check_out_time | TIMESTAMPTZ | optional | last detection |
| presence_score | DECIMAL(5,2) | optional | computed score |
| created_at | TIMESTAMPTZ | DEFAULT now() | audit |
| updated_at | TIMESTAMPTZ | DEFAULT now() | audit |

## Constraints and Indexes
- UNIQUE `(student_id, schedule_id, date)`
- `idx_attendance_student_date`
- `idx_attendance_schedule_date`
- `idx_attendance_status`
