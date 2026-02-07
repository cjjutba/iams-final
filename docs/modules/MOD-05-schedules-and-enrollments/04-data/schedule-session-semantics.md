# Schedule and Session Semantics

## Definitions
- Schedule: class slot with day/time and room/faculty context.
- Current class: schedule where current date/time is within schedule window.
- Session: one date-specific instance of schedule.
- Active schedule: `is_active=true` and valid term context.

## Time Rules
1. Use one consistent timezone for comparisons.
2. Compare current time against `[start_time, end_time]`.
3. If overlaps exist, apply deterministic resolution rule.

## Integration Impact
Attendance and presence computations depend on these semantics.
