# Schedule Screen Flows

## Student Schedule Flow
1. Open `SCR-012`.
2. Fetch schedules via `GET /schedules/me`.
3. Render weekly schedule grouped by day/time.

## Faculty Schedule Flow
1. Open `SCR-020`.
2. Fetch schedules via `GET /schedules/me`.
3. Render teaching schedule grouped by day/time.

## Optional Detail Flow
1. Select schedule item.
2. Call `GET /schedules/{id}` for detailed context.
3. Optionally load roster via `GET /schedules/{id}/students` in class detail views.
