# Presence Tracking and Early Leave Module Catalog

## Subdomains
1. Session Lifecycle Management
- Create and maintain schedule/date session state.

2. Scan Processing
- Evaluate detection outcomes per scan cycle.

3. Miss Counter Management
- Increment/reset counters based on detection results.

4. Early-Leave Detection
- Flag and record events at threshold.

5. Score Computation
- Calculate presence score from scan aggregates.

6. Presence Data Exposure
- Return presence logs and early-leave records.

## Function Catalog
| Function ID | Name | Summary |
|---|---|---|
| FUN-07-01 | Start and Manage Session | initialize and manage session state |
| FUN-07-02 | Run Periodic Scan | evaluate per-scan detection data |
| FUN-07-03 | Track Miss Counters | update per-student miss counters |
| FUN-07-04 | Flag Early Leave | create event when threshold reached |
| FUN-07-05 | Compute Presence Score | compute attendance presence percentage |
| FUN-07-06 | Expose Presence Data | provide logs and early-leave endpoints |

## Actors
- Presence service
- Faculty viewers
- Attendance module
- Notification module

## Interfaces
- Presence endpoints (`/presence/*`)
- `presence_logs`, `early_leave_events`, and `attendance_records` tables
