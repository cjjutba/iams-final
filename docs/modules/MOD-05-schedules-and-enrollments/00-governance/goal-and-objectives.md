# Goal and Objectives

## Module Goal
Define and expose schedule and enrollment data accurately so attendance and presence modules operate on correct class rosters and time windows.

## Auth Context
All MOD-05 endpoints require Supabase JWT (`Authorization: Bearer <token>`). Schedule creation (`POST /schedules`) is admin-only. Role-scoped queries enforce faculty/student data boundaries via JWT `sub` and `role` claims.

## Primary Objectives
1. Provide schedule listing and retrieval APIs with day/time filtering (`day_of_week` 0-6, `start_time`/`end_time` as TIME type).
2. Support admin schedule creation with payload validation (`start_time < end_time`, valid `faculty_id`/`room_id` FK references).
3. Return role-aware schedule views: faculty sees teaching schedules (by `faculty_id`), student sees enrolled schedules (via `enrollments` table).
4. Return enrolled student roster per schedule with access control (faculty/admin/enrolled students only).
5. Enforce schedule and enrollment integrity constraints (unique `(student_id, schedule_id)`, valid FK references).
6. Provide schedule context for downstream modules: MOD-04 (room-to-schedule mapping), MOD-06 (attendance), MOD-07 (presence tracking).

## Success Outcomes
- Schedule queries return accurate day/time-filtered results with deterministic ordering.
- Enrollment relationships are enforced with uniqueness guarantees.
- Role-aware queries return only relevant schedule records (no cross-user data leakage).
- Schedule ownership and access policies are consistently enforced via Supabase JWT.
- Downstream modules can reliably determine "current class" from schedule data.

## Non-Goals (for MOD-05 MVP)
- Full schedule management UI for admin.
- Complex timetable optimizer.
- Multi-campus scheduling orchestration.
- Direct enrollment creation API (enrollments are seeded via MOD-11 import scripts for MVP).
- Rate limiting (thesis demonstration).
- Automatic schedule deactivation based on academic calendar.

## Stakeholders
- Students: view assigned class schedules.
- Faculty: view teaching schedules, view class rosters.
- Admin/operations: create and maintain schedules.
- Attendance/presence modules (MOD-06/MOD-07): consume schedule context.
- Edge device pipeline (MOD-04): uses room_id to infer active schedule.
