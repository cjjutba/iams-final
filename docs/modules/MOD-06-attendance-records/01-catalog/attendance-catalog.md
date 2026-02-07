# Attendance Records Module Catalog

## Subdomains
1. Attendance Marking
- Create/update attendance rows from recognition events.

2. Daily Class Attendance View
- Return today's roster, statuses, and summary counts.

3. Student History View
- Return attendance timeline for student date range.

4. Class History Query
- Return filtered attendance records for schedule/date windows.

5. Manual Attendance Operations
- Faculty override/create attendance rows with remarks.

6. Live Attendance Session View
- Return active session roster and current detection state.

## Function Catalog
| Function ID | Name | Summary |
|---|---|---|
| FUN-06-01 | Mark Attendance | mark/check-in/update attendance row from recognition |
| FUN-06-02 | Get Today's Attendance | class summary and records for current date |
| FUN-06-03 | Get My Attendance | student personal attendance history |
| FUN-06-04 | Get Attendance History | filtered class attendance list |
| FUN-06-05 | Manual Attendance Entry | faculty manual entry/override |
| FUN-06-06 | Get Live Attendance | active class roster with live statuses |

## Actors
- Student
- Faculty
- Backend recognition pipeline
- Attendance service

## Interfaces
- REST attendance endpoints (`/attendance/*`)
- `attendance_records` table
- schedule/user mappings
