# Module Specification

## Module ID
`MOD-05`

## Purpose
Define class schedules and enroll students per class.

## Core Functions
- `FUN-05-01`: List schedules by filters/day.
- `FUN-05-02`: Get schedule by ID.
- `FUN-05-03`: Create schedule (admin).
- `FUN-05-04`: Get schedules for current user.
- `FUN-05-05`: Get students assigned to schedule.

## API Contracts
- `GET /schedules?day=1`
- `GET /schedules/{id}`
- `POST /schedules`
- `GET /schedules/me`
- `GET /schedules/{id}/students`

## Data Dependencies
- `rooms`
- `schedules`
- `enrollments`
- `users`

## Screen Dependencies
- `SCR-012` StudentScheduleScreen
- `SCR-020` FacultyScheduleScreen

## Done Criteria
- Time/day filters return correct active schedules.
- Enrollment relationships are enforced.
- Schedule ownership and permissions are validated.
