# Function Specifications

## FUN-06-01 Mark Attendance
Goal:
- Upsert attendance row from recognition event with dedup protections.

Inputs:
- Recognized user ID, schedule context, timestamp.

Process:
1. Resolve active schedule for timestamp context.
2. Check existing attendance row for `(student_id, schedule_id, date)`.
3. If missing, create row with check-in data.
4. If present, update relevant fields/state.

Outputs:
- Attendance row created/updated.

Validation Rules:
- Prevent duplicate rows.
- Ignore unknown or unauthorized user context.

## FUN-06-02 Get Today's Attendance
Goal:
- Return today's class attendance records and summary.

Inputs:
- `schedule_id` query param.

Process:
1. Validate schedule ID.
2. Query today's attendance rows.
3. Compute summary counts by status.

Outputs:
- Schedule data, attendance records, and summary block.

Validation Rules:
- Return `404` for unknown schedule.
- Enforce authorized access policy.

## FUN-06-03 Get My Attendance
Goal:
- Return authenticated student's attendance history within date range.

Inputs:
- `start_date`, `end_date` query params.

Process:
1. Validate date range.
2. Query rows for current student.
3. Return sorted history entries.

Outputs:
- Attendance history list.

Validation Rules:
- Non-student role should be rejected or policy-routed.
- Invalid date ranges return validation errors.

## FUN-06-04 Get Attendance History
Goal:
- Return filtered attendance records for class/reporting context.

Inputs:
- `schedule_id`, `start_date`, `end_date` query params.

Process:
1. Validate filters.
2. Query attendance records with pagination if supported.
3. Return result set and paging metadata.

Outputs:
- Filtered attendance data.

Validation Rules:
- Unauthorized caller must be blocked.
- Missing mandatory filters should fail validation.

## FUN-06-05 Manual Attendance Entry
Goal:
- Allow faculty to insert/update attendance status manually with remarks.

Inputs:
- `student_id`, `schedule_id`, `date`, `status`, `remarks`.

Process:
1. Validate payload and role.
2. Upsert target attendance row.
3. Persist remarks/audit metadata.

Outputs:
- Created/updated manual attendance record.

Validation Rules:
- Student caller must be rejected.
- Status must be one of allowed values.

## FUN-06-06 Get Live Attendance
Goal:
- Return active class roster with current attendance/session indicators.

Inputs:
- Path param `schedule_id`.

Process:
1. Validate schedule/session context.
2. Resolve current scan/session state.
3. Return per-student live status fields.

Outputs:
- Live attendance payload with session metadata.

Validation Rules:
- Return clear inactive-session response when session not active.
- Enforce faculty/authorized role visibility.
