# Screen State Matrix

| Screen | Loading | Success | Validation/Error | Network Error |
|---|---|---|---|---|
| SCR-012 StudentScheduleScreen | show skeleton/loading list | render weekly schedule | show empty schedule state | retry + cached view |
| SCR-020 FacultyScheduleScreen | show skeleton/loading list | render teaching schedule | show empty schedule state | retry + cached view |

## Required UX Rules
- Display clear empty-state when no schedules are assigned.
- Keep ordering consistent by day/time.
- Surface retry action on transient failures.
