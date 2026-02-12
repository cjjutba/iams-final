# Glossary

- **Session:** Date-specific runtime instance of a schedule, scoped by `(schedule_id, date)` using configured `TIMEZONE`.
- **Scan Cycle:** One periodic detection evaluation pass at `SCAN_INTERVAL` (default: 60 seconds).
- **Miss Counter:** Count of consecutive scans where a student was not detected.
- **Early Leave:** Flag set when miss counter reaches `EARLY_LEAVE_THRESHOLD` (default: 3 consecutive misses). Stored in `early_leave_events` table.
- **Presence Score:** `(scans_detected / total_scans) × 100`. Computed per attendance record.
- **Recovery:** State where a previously missed student is detected again and their miss counter resets to 0.
- **Presence Log:** Individual scan result record stored in `presence_logs` table (FK → `attendance_records.id`).
- **Supabase JWT:** JSON Web Token issued by Supabase Auth. Required for all user-facing MOD-07 endpoints. Contains `sub` (user ID) and `role` claims.
- **System-Internal Function:** Service-layer logic invoked by the presence scan loop, not exposed as HTTP endpoints (FUN-07-01 to FUN-07-05).
- **Timezone:** Configured via `TIMEZONE` env var (default: Asia/Manila, +08:00). Used for session boundaries and "today" queries.
- **Attendance Record:** MOD-06 record that presence logs reference. FK relationship: `presence_logs.attendance_id` → `attendance_records.id`.
- **Cascade Deletion:** User deletion (MOD-02) cascades to attendance_records (MOD-06), which cascades to presence_logs and early_leave_events (MOD-07).
