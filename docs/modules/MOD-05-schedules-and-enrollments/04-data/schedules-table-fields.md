# Schedules Table Fields

## Table
`schedules`

## Module-Relevant Columns
| Column | Type | Constraints | Use in MOD-05 |
|---|---|---|---|
| id | UUID | PK | schedule identifier |
| subject_code | VARCHAR(20) | NOT NULL | class code |
| subject_name | VARCHAR(255) | NOT NULL | class title |
| faculty_id | UUID | FK users | teaching faculty |
| room_id | UUID | FK rooms | classroom mapping |
| day_of_week | INTEGER | 0-6 | day filter |
| start_time | TIME | NOT NULL | session start |
| end_time | TIME | NOT NULL | session end |
| semester | VARCHAR(20) | optional | term metadata |
| academic_year | VARCHAR(20) | optional | year metadata |
| is_active | BOOLEAN | DEFAULT true | active schedule state |

## Indexes
- `idx_schedule_faculty`
- `idx_schedule_room`
- `idx_schedule_day_time`
