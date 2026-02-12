# Schedules Table Fields

## Table
`schedules`

## Module-Relevant Columns
| Column | Type | Constraints | Use in MOD-05 |
|---|---|---|---|
| id | UUID | PK | schedule identifier |
| subject_code | VARCHAR(20) | NOT NULL | class code (e.g., "CS101") |
| subject_name | VARCHAR(255) | NOT NULL | class title (e.g., "Programming 1") |
| faculty_id | UUID | FK → users | teaching faculty (must have role="faculty") |
| room_id | UUID | FK → rooms | classroom mapping |
| day_of_week | INTEGER | 0-6, NOT NULL | day filter (0=Sunday, 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday, 6=Saturday) |
| start_time | TIME | NOT NULL | session start (interpreted in configured timezone) |
| end_time | TIME | NOT NULL | session end (must be > start_time) |
| semester | VARCHAR(20) | optional | term metadata (e.g., "1st Sem") |
| academic_year | VARCHAR(20) | optional | year metadata (e.g., "2025-2026") |
| is_active | BOOLEAN | DEFAULT true | active schedule state (manual toggle in MVP) |
| created_at | TIMESTAMPTZ | DEFAULT now() | record creation timestamp |

## day_of_week Mapping
| Value | Day |
|---|---|
| 0 | Sunday |
| 1 | Monday |
| 2 | Tuesday |
| 3 | Wednesday |
| 4 | Thursday |
| 5 | Friday |
| 6 | Saturday |

## Indexes
- `idx_schedule_faculty` on (faculty_id)
- `idx_schedule_room` on (room_id)
- `idx_schedule_day_time` on (day_of_week, start_time)

## Timezone Note
`start_time` and `end_time` are stored as TIME type (no timezone info). Interpretation uses the configured `TIMEZONE` env var (default: Asia/Manila for JRMSU pilot).
