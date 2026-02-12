# Presence Tracking and Early Leave Module Catalog

## Auth Context
- **System-Internal (FUN-07-01 to FUN-07-05):** Invoked by the presence service scan loop — no HTTP endpoints, no JWT.
- **User-Facing (FUN-07-06):** Supabase JWT required, faculty/admin role. Returns 401/403 for auth failures.

## Subdomains
1. **Session Lifecycle Management**
   - Create and maintain schedule/date session state using configured `TIMEZONE`.
   - Auth: system-internal (no JWT).

2. **Scan Processing**
   - Evaluate detection outcomes per scan cycle at `SCAN_INTERVAL` (default: 60s).
   - Auth: system-internal (no JWT).

3. **Miss Counter Management**
   - Increment/reset counters based on detection results (deterministic logic).
   - Auth: system-internal (no JWT).

4. **Early-Leave Detection**
   - Flag and record events at `EARLY_LEAVE_THRESHOLD` (default: 3 consecutive misses).
   - Auth: system-internal (no JWT).

5. **Score Computation**
   - Calculate presence score: `(scans_detected / total_scans) × 100`.
   - Auth: system-internal (no JWT).

6. **Presence Data Exposure**
   - Return presence logs and early-leave records via authenticated API.
   - Auth: Supabase JWT, faculty/admin role.

## Function Catalog
| Function ID | Name | Summary | Auth | Type |
|---|---|---|---|---|
| FUN-07-01 | Start and Manage Session | Initialize and manage session state | system-internal | service |
| FUN-07-02 | Run Periodic Scan | Evaluate per-scan detection data | system-internal | service |
| FUN-07-03 | Track Miss Counters | Update per-student miss counters | system-internal | service |
| FUN-07-04 | Flag Early Leave | Create event when threshold reached | system-internal | service |
| FUN-07-05 | Compute Presence Score | Compute attendance presence percentage | system-internal | service |
| FUN-07-06 | Expose Presence Data | Provide logs and early-leave endpoints | Supabase JWT (faculty/admin) | API |

## Actors
- **Presence service** — system-internal actor for FUN-07-01 to FUN-07-05 (scan loop, counters, flagging).
- **Faculty** — authenticated users querying presence data via FUN-07-06 (Supabase JWT, faculty role).
- **Admin** — authenticated users with unrestricted access to FUN-07-06 endpoints.
- **MOD-06 (Attendance module)** — provides attendance records that presence logs reference.
- **MOD-08 (Notification module)** — consumes early-leave events for WebSocket broadcast.

## Interfaces
- Base path: `/api/v1/presence`
- Endpoints: `GET /presence/{attendance_id}/logs`, `GET /presence/early-leaves`
- SQLAlchemy models: `PresenceLog`, `EarlyLeaveEvent`
- Tables: `presence_logs` (FK → `attendance_records.id`), `early_leave_events` (FK → `attendance_records.id`, `schedules.id`)
- Response envelope: `{ "success": true, "data": {}, "message": "" }`
