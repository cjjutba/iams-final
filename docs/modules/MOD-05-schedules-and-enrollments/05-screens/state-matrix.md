# Screen State Matrix

| Screen | Loading | Success | Empty State | Auth Error (401) | Permission Error (403) | Network Error |
|---|---|---|---|---|---|---|
| SCR-012 StudentScheduleScreen | show skeleton/loading list | render weekly schedule grouped by day | "No schedules assigned" message | redirect to login | show forbidden message | retry + cached view |
| SCR-020 FacultyScheduleScreen | show skeleton/loading list | render teaching schedule grouped by day | "No teaching schedules" message | redirect to login | show forbidden message | retry + cached view |

## Required UX Rules
- Display clear empty-state when no schedules are assigned.
- Keep ordering consistent by `day_of_week` ASC, `start_time` ASC.
- Surface retry action on transient failures.
- Handle 401 (expired JWT) by redirecting to login with appropriate message.
- Handle 403 (unauthorized access) by showing "Access denied" message.
- Pull-to-refresh available on schedule list.
