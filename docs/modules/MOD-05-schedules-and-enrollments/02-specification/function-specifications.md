# Function Specifications

## FUN-05-01 List Schedules
Goal:
- Return schedule list filtered by day and other optional query inputs.

Inputs:
- Query params (`day`, pagination/filter options as defined).

Process:
1. Validate query params.
2. Query active schedules with filters.
3. Return normalized schedule summaries.

Outputs:
- `200` with schedule list.

Validation Rules:
- Reject invalid day/time filter formats.
- Ensure deterministic sort order (day/time).

## FUN-05-02 Get Schedule
Goal:
- Return full schedule details by ID.

Inputs:
- Path param `id` (UUID).

Process:
1. Validate ID.
2. Query schedule by ID.
3. Return schedule payload.

Outputs:
- `200` with schedule data.

Validation Rules:
- Return `404` when schedule not found.

## FUN-05-03 Create Schedule
Goal:
- Create a new schedule record with admin authorization.

Inputs:
- Subject fields, faculty_id, room_id, day_of_week, start_time, end_time.

Process:
1. Validate payload and time window (`start_time < end_time`).
2. Authorize admin caller.
3. Validate referenced faculty/room records.
4. Persist schedule and return created record.

Outputs:
- `201` with created schedule.

Validation Rules:
- Reject invalid references or malformed time values.
- Reject unauthorized caller.

## FUN-05-04 Get My Schedules
Goal:
- Return schedules for current authenticated user (student or faculty).

Inputs:
- Authenticated user context.

Process:
1. Resolve caller role.
2. For faculty: query schedules by `faculty_id`.
3. For student: query schedules via `enrollments`.
4. Return role-scoped schedule list.

Outputs:
- `200` with schedule list.

Validation Rules:
- Return `403` for unsupported role context.

## FUN-05-05 Get Schedule Students
Goal:
- Return enrolled students for one schedule.

Inputs:
- Path param `id` (schedule UUID).

Process:
1. Validate schedule ID.
2. Query enrollments joined with user student profile fields.
3. Return roster list.

Outputs:
- `200` with student list.

Validation Rules:
- Return `404` if schedule not found.
- Enforce permission policy for who can view roster.
