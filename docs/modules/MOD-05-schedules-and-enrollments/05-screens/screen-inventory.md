# Screen Inventory (MOD-05)

## Included Screens
| Screen ID | Screen Name | Role | Schedule Module Usage | Auth |
|---|---|---|---|---|
| SCR-012 | StudentScheduleScreen | Student | view enrolled weekly schedule | Supabase JWT (student) |
| SCR-020 | FacultyScheduleScreen | Faculty | view teaching weekly schedule | Supabase JWT (faculty) |

## Screen-to-Function Mapping
- `SCR-012` → `FUN-05-04` (primary: get my schedules) and optional `FUN-05-01` (list all schedules)
- `SCR-020` → `FUN-05-04` (primary: get my schedules) and optional `FUN-05-01` (list all schedules)

## API Calls per Screen
- **SCR-012**: `GET /api/v1/schedules/me` (primary), `GET /api/v1/schedules/{id}` (detail tap), `GET /api/v1/schedules/{id}/students` (roster view)
- **SCR-020**: `GET /api/v1/schedules/me` (primary), `GET /api/v1/schedules/{id}` (detail tap), `GET /api/v1/schedules/{id}/students` (roster view)
