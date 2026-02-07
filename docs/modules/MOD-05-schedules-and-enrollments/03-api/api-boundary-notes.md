# API Boundary Notes

## Owned by MOD-05
- `/schedules` endpoint family and roster retrieval behavior.

## Related but Owned by Other Modules
- Attendance APIs in `MOD-06` consume schedule IDs and session semantics.
- Presence APIs in `MOD-07` consume active schedule and enrolled student context.
- Import/seed logic for schedule CSV is owned by `MOD-11`.

## Coordination Rule
Changes to schedule identity or timing fields must be synchronized with attendance, presence, and import modules.
