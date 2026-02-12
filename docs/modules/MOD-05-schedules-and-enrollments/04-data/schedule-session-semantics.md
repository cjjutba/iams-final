# Schedule and Session Semantics

## Definitions
- **Schedule**: Immutable class slot metadata: `subject_code`, `subject_name`, `faculty_id`, `room_id`, `day_of_week`, `start_time`, `end_time`, `semester`, `academic_year`, `is_active`.
- **Active Schedule**: Schedule where `is_active=true`. Optional `semester`/`academic_year` provide scope context but are not auto-enforced in MVP.
- **Current Class**: The schedule for which:
  - `is_active=true`
  - `day_of_week` matches today (0=Sunday, 1=Monday, ..., 6=Saturday)
  - Current time (in configured timezone) falls within `[start_time, end_time]`
  - If multiple schedules match for the same room, backend uses the one with earliest `start_time` or documented tiebreaker rule.
- **Session**: One date-specific instance of a schedule (e.g., "CS101 on 2026-02-12").
- **Enrolled Student**: User with `role="student"` and an enrollment record for that schedule.

## Timezone Configuration
- All time comparisons use the configured timezone (`TIMEZONE` env var).
- Default for JRMSU pilot: Asia/Manila (+08:00).
- `start_time` and `end_time` are stored as TIME type (no timezone info); interpretation assumes `TIMEZONE` setting.
- Current time comparison: compare `CURRENT_TIME` (in configured timezone) against schedule `[start_time, end_time]` window.

## Time Rules
1. `start_time` must be strictly less than `end_time` (enforced at creation time).
2. Time comparisons for "current class" detection use configured timezone consistently.
3. If overlapping schedules exist for the same room at the same time, apply deterministic resolution rule (earliest `start_time`, then `created_at`).

## Query Semantics
- `GET /schedules?day=1`: Returns all schedules with `is_active=true` and `day_of_week=1`, regardless of current time.
- `GET /schedules/me`: Faculty returns schedules by `faculty_id` and `is_active=true`. Student returns schedules from enrollments with `is_active=true`.
- List operations do NOT filter by current time or academic calendar; filtering is done at application logic level (MOD-06/MOD-07) when determining "current class."

## Integration Impact
- **MOD-06 (Attendance)**: Uses schedule `start_time`/`end_time` to determine session boundaries for attendance records.
- **MOD-07 (Presence Tracking)**: Uses "current class" detection to scope 60-second scan intervals and enrolled student list for presence scoring.
- **MOD-04 (Edge Device)**: Backend determines "current class" from `room_id` → schedules mapping when processing face detections.
