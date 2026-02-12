# Function Specifications

## FUN-05-01 List Schedules
Goal:
- Return schedule list filtered by day and other optional query inputs.

Auth:
- Requires Supabase JWT (`Authorization: Bearer <token>`). All roles (student, faculty, admin).

Inputs:
- Query params:
  - `day` (INTEGER 0-6, optional): Filter by `day_of_week` (0=Sunday, 1=Monday, ..., 6=Saturday).
  - `room_id` (UUID, optional): Filter by room.
  - `faculty_id` (UUID, optional): Filter by faculty.
  - `active_only` (BOOLEAN, optional, default=true): Filter by `is_active=true`.

Process:
1. Verify Supabase JWT is present and valid; return 401 if not.
2. Validate query params (reject invalid `day` values outside 0-6).
3. Build WHERE clause: `is_active=true` (if `active_only`), `day_of_week` (if `day`), `room_id` (if provided), `faculty_id` (if provided).
4. Query active schedules with filters.
5. Sort by `day_of_week` ASC, `start_time` ASC.
6. Return normalized schedule summaries.

Outputs:
- `200` with schedule list (`{ "success": true, "data": [...], "message": "" }`).
- `400` if invalid query params.
- `401` if missing/invalid JWT.

Validation Rules:
- Reject invalid day/time filter formats.
- Ensure deterministic sort order (`day_of_week` ASC, `start_time` ASC).

## FUN-05-02 Get Schedule
Goal:
- Return full schedule details by ID.

Auth:
- Requires Supabase JWT. All roles.

Inputs:
- Path param `id` (UUID).

Process:
1. Verify Supabase JWT; return 401 if not valid.
2. Validate ID format.
3. Query schedule by ID (include faculty name, room name via joins).
4. Return schedule payload.

Outputs:
- `200` with schedule data (`{ "success": true, "data": {...}, "message": "" }`).
- `401` if missing/invalid JWT.
- `404` if schedule not found.

Validation Rules:
- Return `404` when schedule not found.

## FUN-05-03 Create Schedule
Goal:
- Create a new schedule record with admin authorization.

Auth:
- Requires Supabase JWT with `role == "admin"`. Returns 403 if caller is not admin.

Inputs:
- `subject_code` (VARCHAR(20), required): Course code (e.g., "CS101").
- `subject_name` (VARCHAR(255), required): Course name.
- `faculty_id` (UUID, required): FK to `users` table (must be a faculty user).
- `room_id` (UUID, required): FK to `rooms` table.
- `day_of_week` (INTEGER 0-6, required): 0=Sunday, 1=Monday, ..., 6=Saturday.
- `start_time` (TIME, required): Class start time (e.g., "08:00:00").
- `end_time` (TIME, required): Class end time (e.g., "10:00:00").
- `semester` (VARCHAR(20), optional): Term metadata.
- `academic_year` (VARCHAR(20), optional): Year metadata.

Process:
1. Verify Supabase JWT; return 401 if missing/invalid.
2. Verify JWT `role` claim == `"admin"`; return 403 if not.
3. Validate payload: `start_time < end_time`, all required fields present.
4. Validate referenced `faculty_id` exists in users table with faculty role.
5. Validate referenced `room_id` exists in rooms table.
6. Persist schedule (set `is_active=true` by default).
7. Return created record.

Outputs:
- `201` with created schedule (`{ "success": true, "data": {...}, "message": "Schedule created successfully" }`).
- `400` if invalid payload, time values, or FK references.
- `401` if missing/invalid JWT.
- `403` if non-admin caller.

Validation Rules:
- `start_time` must be strictly less than `end_time`.
- `faculty_id` must reference an existing user with `role == "faculty"`.
- `room_id` must reference an existing room.
- `day_of_week` must be integer 0-6.

## FUN-05-04 Get My Schedules
Goal:
- Return schedules for current authenticated user (student or faculty).

Auth:
- Requires Supabase JWT. Scoped by JWT `sub` (user ID) and `role` claim.

Inputs:
- Authenticated user context (from JWT: `sub` = user ID, `role` = user role).

Process:
1. Verify Supabase JWT; return 401 if missing/invalid.
2. Extract `sub` (user ID) and `role` from JWT.
3. If role=faculty: Query schedules WHERE `faculty_id = JWT sub` AND `is_active=true`. Returns teaching schedules.
4. If role=student: Query enrollments WHERE `student_id = JWT sub`, JOIN schedules WHERE `is_active=true`. Returns enrolled schedules.
5. If role=admin: Return all active schedules (or treat as faculty if admin also teaches).
6. Sort by `day_of_week` ASC, `start_time` ASC.
7. Return role-scoped schedule list.

Outputs:
- `200` with schedule list (`{ "success": true, "data": [...], "message": "" }`).
- `401` if missing/invalid JWT.
- `403` if unsupported role context.

Validation Rules:
- Faculty can only see own teaching schedules (by `faculty_id`).
- Student can only see own enrolled schedules (via `enrollments` join).
- Return `403` for unsupported role context.

## FUN-05-05 Get Schedule Students
Goal:
- Return enrolled students for one schedule.

Auth:
- Requires Supabase JWT. Restricted to:
  - Admin (full access).
  - Faculty assigned to this schedule (`faculty_id` matches JWT `sub`).
  - Students enrolled in this schedule (has enrollment record).

Inputs:
- Path param `id` (schedule UUID).

Process:
1. Verify Supabase JWT; return 401 if missing/invalid.
2. Validate schedule exists; return 404 if not.
3. Check access control:
   - If admin: allow.
   - If faculty: check `schedule.faculty_id == JWT sub`; return 403 if not.
   - If student: check enrollment exists for `(JWT sub, schedule_id)`; return 403 if not.
4. Query enrollments JOIN users WHERE `schedule_id` matches.
5. Return roster list (user ID, student_id, first_name, last_name).

Outputs:
- `200` with student list (`{ "success": true, "data": [...], "message": "" }`).
- `401` if missing/invalid JWT.
- `403` if caller not authorized to view roster.
- `404` if schedule not found.

Validation Rules:
- Return `404` if schedule not found.
- Return `403` if caller is not admin, not the assigned faculty, and not an enrolled student.
- Roster response includes: `id` (users.id), `student_id` (users.student_id), `first_name`, `last_name`.
