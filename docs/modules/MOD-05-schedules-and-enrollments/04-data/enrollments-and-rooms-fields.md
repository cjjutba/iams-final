# Enrollments and Rooms Fields

## Enrollments Table (`enrollments`)
| Column | Type | Constraints | Use |
|---|---|---|---|
| id | UUID | PK | row id |
| student_id | UUID | FK users | enrolled student |
| schedule_id | UUID | FK schedules | class mapping |
| enrolled_at | TIMESTAMPTZ | DEFAULT now() | audit timestamp |

### Constraints
- UNIQUE `(student_id, schedule_id)`

## Rooms Table (`rooms`)
| Column | Type | Constraints | Use |
|---|---|---|---|
| id | UUID | PK | room id |
| name | VARCHAR(100) | NOT NULL | room label |
| building | VARCHAR(100) | optional | location context |
| capacity | INTEGER | optional | capacity rules |
| camera_endpoint | VARCHAR(255) | optional | edge mapping |
| is_active | BOOLEAN | DEFAULT true | active room |
