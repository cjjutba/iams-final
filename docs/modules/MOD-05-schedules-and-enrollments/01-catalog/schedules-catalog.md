# Schedules and Enrollments Module Catalog

## Subdomains
1. Schedule Querying
- List and retrieve schedule records.

2. Schedule Creation
- Create new schedule entries with validation.

3. Role-Aware Schedule View
- Resolve schedule list for current user context.

4. Enrollment Roster Access
- Return enrolled students for a schedule.

## Function Catalog
| Function ID | Name | Summary |
|---|---|---|
| FUN-05-01 | List Schedules | Return schedules by filter/day |
| FUN-05-02 | Get Schedule | Return schedule by ID |
| FUN-05-03 | Create Schedule | Create schedule record (admin) |
| FUN-05-04 | Get My Schedules | Return current user schedule list |
| FUN-05-05 | Get Schedule Students | Return enrolled students per schedule |

## Actors
- Admin
- Student
- Faculty
- Backend schedule service

## Interfaces
- REST schedule endpoints (`/schedules/*`)
- `schedules`, `enrollments`, `rooms`, and `users` data tables
