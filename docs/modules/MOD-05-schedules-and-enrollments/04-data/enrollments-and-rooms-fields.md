# Enrollments and Rooms Fields

## Enrollments Table (`enrollments`)
| Column | Type | Constraints | Use |
|---|---|---|---|
| id | UUID | PK | row id |
| student_id | UUID | FK → users | enrolled student (must have role="student") |
| schedule_id | UUID | FK → schedules | class mapping |
| enrolled_at | TIMESTAMPTZ | DEFAULT now() | audit timestamp |

### Constraints
- UNIQUE `(student_id, schedule_id)` — prevents duplicate enrollments.

### Indexes
- `idx_enrollment_student` on (student_id)
- `idx_enrollment_schedule` on (schedule_id)

### Enrollment Lifecycle
- **Creation**: Via MOD-11 import scripts or direct DB operations. No enrollment API in MVP.
- **Cascade deletion**: When a student is deleted (MOD-02), all enrollment rows for that student are cascade-deleted.
- **Schedule deactivation**: When `schedule.is_active=false`, enrollments remain in DB (historical preservation). Active queries filter schedules by `is_active=true`.
- **No soft delete on enrollments**: Rows are either present or cascade-deleted. No `is_active` column on enrollments.

## Rooms Table (`rooms`)
| Column | Type | Constraints | Use |
|---|---|---|---|
| id | UUID | PK | room id |
| name | VARCHAR(100) | NOT NULL | room label (e.g., "Room 301") |
| building | VARCHAR(100) | optional | location context |
| capacity | INTEGER | optional | capacity rules |
| camera_endpoint | VARCHAR(255) | optional | edge device mapping (MOD-04) |
| is_active | BOOLEAN | DEFAULT true | active room |

### Rooms-to-Schedules Relationship
- `schedules.room_id` FK references `rooms.id`.
- One room can have multiple schedules (different days/times).
- MOD-04 edge device uses `room_id` to identify which room face detections come from; backend maps this to active schedule context.
