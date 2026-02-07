# Function Specifications

## FUN-07-01 Start and Manage Session State
Goal:
- Initialize and maintain session state for schedule/date context.

Inputs:
- schedule_id, date, enrolled student set.

Process:
1. Resolve active schedule/session boundaries.
2. Initialize per-student state fields.
3. Track session lifecycle (start/active/end).

Outputs:
- Session state object bound to schedule/date.

Validation Rules:
- Reject invalid/non-active schedule context.
- Ensure timezone-consistent date/time handling.

## FUN-07-02 Run Periodic Scan
Goal:
- Execute scan cycle and update detection state.

Inputs:
- latest detection set, current session state.

Process:
1. Iterate enrolled students.
2. Determine detected/not-detected status per scan.
3. Update scan counters and logs.

Outputs:
- Updated per-student scan state and log entries.

Validation Rules:
- Scan interval should use configured value.
- Missing detections should not break loop.

## FUN-07-03 Maintain Miss Counters
Goal:
- Track consecutive misses and recovery resets.

Inputs:
- per-student detection result.

Process:
1. If detected: reset miss_count.
2. If not detected: increment miss_count.
3. Persist counter and last-seen updates.

Outputs:
- Updated miss_count and last_seen fields.

Validation Rules:
- Counter must never go negative.
- Recovery detection should reset to zero deterministically.

## FUN-07-04 Flag Early Leave
Goal:
- Create early-leave event once threshold condition is met.

Inputs:
- per-student miss_count, threshold config.

Process:
1. Compare miss_count against threshold.
2. If reached and not previously flagged, create early-leave event.
3. Update related attendance status context.

Outputs:
- Early-leave event records and flag state.

Validation Rules:
- Avoid duplicate flagging for same attendance/session context.
- Threshold must be configurable.

## FUN-07-05 Compute Presence Score
Goal:
- Compute student presence percentage for session.

Inputs:
- total_scans, scans_detected.

Process:
1. Validate denominator.
2. Compute `score = scans_detected / total_scans * 100`.
3. Persist/update score in attendance context.

Outputs:
- Numeric presence score.

Validation Rules:
- If total_scans is zero, handle safely (score baseline policy).

## FUN-07-06 Return Presence Logs and Early-Leave Events
Goal:
- Expose presence logs and early-leave events through read APIs.

Inputs:
- attendance_id or schedule/date filters.

Process:
1. Validate query identifiers.
2. Query logs/events from respective tables.
3. Return normalized response payloads.

Outputs:
- Presence log list and early-leave event list.

Validation Rules:
- Enforce role/ownership access rules.
- Return empty lists when no records exist.
