# Schedules and Enrollments Module Catalog

## Auth Context
All endpoints require Supabase JWT (`Authorization: Bearer <token>`). Schedule creation is admin-only. Roster access is restricted to faculty/admin/enrolled students.

## Subdomains
1. Schedule Querying
- List and retrieve schedule records filtered by `day_of_week` (0-6), with deterministic sort by day/time.
- Auth: Supabase JWT (all roles).

2. Schedule Creation
- Create new schedule entries with admin authorization and payload validation (`start_time < end_time`, valid FK references).
- Auth: Supabase JWT with `role == "admin"`.

3. Role-Aware Schedule View
- Resolve schedule list for current user: faculty by `faculty_id`, student by `enrollments` table join.
- Auth: Supabase JWT, scoped by JWT `sub` and `role`.

4. Enrollment Roster Access
- Return enrolled students for a schedule with access control.
- Auth: Supabase JWT, restricted to faculty assigned to schedule, enrolled students, or admin.

## Function Catalog
| Function ID | Name | Summary |
|---|---|---|
| FUN-05-01 | List Schedules | Return active schedules filtered by `day_of_week` and optional params |
| FUN-05-02 | Get Schedule | Return full schedule details by UUID |
| FUN-05-03 | Create Schedule | Create schedule record (admin-only, Supabase JWT role check) |
| FUN-05-04 | Get My Schedules | Return role-scoped schedule list for authenticated user |
| FUN-05-05 | Get Schedule Students | Return enrolled student roster with access control |

## Actors
- Admin: creates schedules, views all data
- Student: views enrolled schedules, views classmate roster
- Faculty: views teaching schedules, views class roster
- Backend schedule service: serves downstream MOD-06/MOD-07/MOD-04

## Interfaces
- REST schedule endpoints (`/api/v1/schedules/*`) with Supabase JWT auth
- SQLAlchemy models: `Schedule`, `Enrollment`, `Room`, `User`
- `schedules`, `enrollments`, `rooms`, and `users` PostgreSQL tables
