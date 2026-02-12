# Glossary

- **Attendance Record:** Daily status row for a student in a schedule. Stored in `attendance_records` table. Unique per `(student_id, schedule_id, date)`.
- **Check-in Time:** First detection timestamp for attendance date. Stored as TIMESTAMP WITH TIME ZONE. Interpreted using configured timezone (`TIMEZONE` env var).
- **Attendance Status:** One of: `present`, `late`, `absent`, `early_leave`. Stored as VARCHAR in `attendance_records.status`.
- **Presence Score:** Percentage derived from scan detections (from MOD-07 presence module). Formula: `(total_present / total_scans) * 100%`.
- **Manual Override:** Faculty-provided status change with audit `remarks`. Requires faculty or admin role (Supabase JWT). Records `updated_by` and `updated_at`.
- **Live Attendance:** Real-time session roster state for an active class. Reflects current detection state during ongoing schedule.
- **Dedup Rule:** One attendance row per `(student_id, schedule_id, date)`. Enforced at database level with UNIQUE constraint.
- **Supabase JWT:** JSON Web Token issued by Supabase Auth. Required on all MOD-06 endpoints via `Authorization: Bearer <token>`. Contains `sub` (user ID) and `role` claims.
- **Timezone:** Configured via `TIMEZONE` env var (default: Asia/Manila, UTC+08:00 for JRMSU pilot). "Today" queries use current date in configured timezone.
- **Schedule Context:** The `schedule_id` foreign key linking attendance records to a specific class schedule (MOD-05). Required for all attendance operations.
- **Recognition Pipeline:** The system flow from MOD-04 (edge device capture) → MOD-03 (face recognition) → MOD-06 (attendance marking). Attendance is marked automatically, not by user action.
- **Audit Trail:** Manual attendance entries require `remarks` text explaining the override reason. Stored alongside `updated_by` (user ID of faculty/admin who made the change) and `updated_at` timestamp.
