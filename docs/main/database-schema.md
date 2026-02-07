# Database Schema

## Overview
PostgreSQL database with 9 core tables. For IAMS, these tables are hosted in **Supabase** (PostgreSQL 15). Backend and mobile app connect to Supabase for users, schedules, attendance; FAISS index remains on the backend server.

---

## Entity Relationship

```
users ─────────────────┬───────────────────────────────────┬──────────────────┐
  │                    │                                   │                  │
  │ 1:1                │ 1:N                               │ 1:N              │ 1:N
  ▼                    ▼                                   ▼                  ▼
face_registrations   schedules (as faculty)            enrollments      notifications
                       │                                   │
                       │ 1:N                               │
                       ▼                                   │
                   attendance_records ◄────────────────────┘
                       │
                       │ 1:N
                       ├─────────────────┐
                       ▼                 ▼
                 presence_logs    early_leave_events
```

---

## Tables

### users
Stores all system users (students, faculty, admin).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT uuid | Unique identifier |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Login email |
| password_hash | VARCHAR(255) | NOT NULL | Bcrypt hash |
| role | VARCHAR(20) | NOT NULL | student, faculty, admin |
| first_name | VARCHAR(100) | | First name |
| last_name | VARCHAR(100) | | Last name |
| student_id | VARCHAR(50) | UNIQUE | School ID (students only) |
| is_active | BOOLEAN | DEFAULT true | Account status |
| created_at | TIMESTAMPTZ | DEFAULT now() | Creation time |
| updated_at | TIMESTAMPTZ | DEFAULT now() | Last update |

**Indexes:**
- `idx_users_email` on (email)
- `idx_users_student_id` on (student_id)
- `idx_users_role` on (role)

---

### face_registrations
Links users to their face embeddings in FAISS.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| user_id | UUID | FK → users, UNIQUE | One registration per user |
| embedding_id | VARCHAR(255) | NOT NULL | Reference to FAISS index |
| registered_at | TIMESTAMPTZ | DEFAULT now() | Registration time |
| is_active | BOOLEAN | DEFAULT true | Active status |

**Indexes:**
- `idx_face_user` on (user_id)

---

### rooms
Physical classroom locations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| name | VARCHAR(100) | NOT NULL | Room name (e.g., "Room 301") |
| building | VARCHAR(100) | | Building name |
| capacity | INTEGER | | Seating capacity |
| camera_endpoint | VARCHAR(255) | | RPi connection URL |
| is_active | BOOLEAN | DEFAULT true | Active status |

---

### schedules
Class schedules.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| subject_code | VARCHAR(20) | NOT NULL | Course code |
| subject_name | VARCHAR(255) | NOT NULL | Course name |
| faculty_id | UUID | FK → users | Assigned faculty |
| room_id | UUID | FK → rooms | Assigned room |
| day_of_week | INTEGER | 0-6 | 0=Sunday, 1=Monday, etc. |
| start_time | TIME | NOT NULL | Class start |
| end_time | TIME | NOT NULL | Class end |
| semester | VARCHAR(20) | | e.g., "1st Sem" |
| academic_year | VARCHAR(20) | | e.g., "2024-2025" |
| is_active | BOOLEAN | DEFAULT true | Active status |

**Indexes:**
- `idx_schedule_faculty` on (faculty_id)
- `idx_schedule_room` on (room_id)
- `idx_schedule_day_time` on (day_of_week, start_time)

---

### enrollments
Links students to their classes.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| student_id | UUID | FK → users | Enrolled student |
| schedule_id | UUID | FK → schedules | Class enrolled in |
| enrolled_at | TIMESTAMPTZ | DEFAULT now() | Enrollment time |

**Constraints:**
- UNIQUE (student_id, schedule_id)

**Indexes:**
- `idx_enrollment_student` on (student_id)
- `idx_enrollment_schedule` on (schedule_id)

---

### attendance_records
Daily attendance per student per class.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| student_id | UUID | FK → users | Student |
| schedule_id | UUID | FK → schedules | Class |
| date | DATE | NOT NULL | Attendance date |
| status | VARCHAR(20) | NOT NULL | present, late, absent, early_leave |
| check_in_time | TIMESTAMPTZ | | First detection time |
| check_out_time | TIMESTAMPTZ | | Last detection time |
| presence_score | DECIMAL(5,2) | | Percentage present |
| total_scans | INTEGER | DEFAULT 0 | Total scans in session |
| scans_present | INTEGER | DEFAULT 0 | Scans where detected |
| remarks | TEXT | | Manual notes |
| created_at | TIMESTAMPTZ | DEFAULT now() | Record creation |
| updated_at | TIMESTAMPTZ | DEFAULT now() | Last update |

**Constraints:**
- UNIQUE (student_id, schedule_id, date)

**Indexes:**
- `idx_attendance_student_date` on (student_id, date)
- `idx_attendance_schedule_date` on (schedule_id, date)
- `idx_attendance_status` on (status)

---

### presence_logs
Individual scan results during a session.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGSERIAL | PK | Auto-increment ID |
| attendance_id | UUID | FK → attendance_records | Parent record |
| scan_number | INTEGER | NOT NULL | Scan sequence number |
| scan_time | TIMESTAMPTZ | NOT NULL | Time of scan |
| detected | BOOLEAN | NOT NULL | Was student detected? |
| confidence | DECIMAL(5,4) | | Match confidence (0-1) |

**Indexes:**
- `idx_presence_attendance` on (attendance_id)
- `idx_presence_time` on (scan_time)

---

### early_leave_events
Records when students leave early.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| attendance_id | UUID | FK → attendance_records | Related attendance |
| detected_at | TIMESTAMPTZ | NOT NULL | When flagged |
| last_seen_at | TIMESTAMPTZ | | Last detection before flag |
| consecutive_misses | INTEGER | NOT NULL | Misses that triggered flag |
| notified | BOOLEAN | DEFAULT false | Faculty notified? |
| notified_at | TIMESTAMPTZ | | Notification time |

**Indexes:**
- `idx_early_leave_attendance` on (attendance_id)
- `idx_early_leave_time` on (detected_at)

---

### notifications
In-app notifications for users (attendance alerts, system messages).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| user_id | UUID | FK → users | Notification recipient |
| title | VARCHAR(255) | NOT NULL | Notification title |
| message | TEXT | NOT NULL | Notification body |
| type | VARCHAR(50) | NOT NULL | Notification category (attendance, alert, system) |
| read | BOOLEAN | DEFAULT false | Read status |
| read_at | TIMESTAMPTZ | | When the notification was read |
| reference_id | VARCHAR(255) | | Optional reference to related entity (e.g., attendance_id) |
| reference_type | VARCHAR(50) | | Type of referenced entity (e.g., "attendance", "early_leave") |
| created_at | TIMESTAMPTZ | DEFAULT now() | Creation time |

**Indexes:**
- `idx_notifications_user` on (user_id)
- `idx_notifications_type` on (type)
- `idx_notifications_created` on (created_at)

---

## Status Values

### User Roles
| Value | Description |
|-------|-------------|
| student | Can view own attendance |
| faculty | Can view class attendance |
| admin | Full system access |

### Attendance Status
| Value | Description |
|-------|-------------|
| present | Detected on time, stayed throughout |
| late | First detected after grace period |
| absent | Never detected |
| early_leave | Left before class ended |

---

## Relationships Summary

| Parent | Child | Relationship |
|--------|-------|--------------|
| users | face_registrations | 1:1 |
| users | schedules | 1:N (as faculty) |
| users | enrollments | 1:N (as student) |
| users | attendance_records | 1:N |
| users | notifications | 1:N |
| rooms | schedules | 1:N |
| schedules | enrollments | 1:N |
| schedules | attendance_records | 1:N |
| attendance_records | presence_logs | 1:N |
| attendance_records | early_leave_events | 1:1 |

---

## Sample Queries

### Get today's attendance for a class
```sql
SELECT 
  u.first_name,
  u.last_name,
  u.student_id,
  ar.status,
  ar.check_in_time,
  ar.presence_score
FROM attendance_records ar
JOIN users u ON ar.student_id = u.id
WHERE ar.schedule_id = :schedule_id
  AND ar.date = CURRENT_DATE
ORDER BY u.last_name;
```

### Get student's attendance history
```sql
SELECT 
  ar.date,
  s.subject_code,
  s.subject_name,
  ar.status,
  ar.presence_score
FROM attendance_records ar
JOIN schedules s ON ar.schedule_id = s.id
WHERE ar.student_id = :student_id
  AND ar.date BETWEEN :start_date AND :end_date
ORDER BY ar.date DESC;
```

### Get early leaves for today
```sql
SELECT 
  u.first_name,
  u.last_name,
  s.subject_name,
  ele.detected_at,
  ele.consecutive_misses
FROM early_leave_events ele
JOIN attendance_records ar ON ele.attendance_id = ar.id
JOIN users u ON ar.student_id = u.id
JOIN schedules s ON ar.schedule_id = s.id
WHERE ar.date = CURRENT_DATE
  AND ar.schedule_id = :schedule_id;
```

---

## Indexes Strategy

| Query Pattern | Index |
|---------------|-------|
| Login by email | users(email) |
| Get student by school ID | users(student_id) |
| Get attendance by student + date | attendance_records(student_id, date) |
| Get attendance by class + date | attendance_records(schedule_id, date) |
| Get schedules by day | schedules(day_of_week, start_time) |
| Get presence logs | presence_logs(attendance_id) |
