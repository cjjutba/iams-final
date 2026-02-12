# Schedule Screen Flows

## Student Schedule Flow
1. Open `SCR-012` (requires valid Supabase JWT with role=student).
2. Fetch schedules via `GET /api/v1/schedules/me` (returns enrolled schedules).
3. Render weekly schedule grouped by `day_of_week`, sorted by `start_time` ASC.
4. Pull-to-refresh to reload schedule data.

## Faculty Schedule Flow
1. Open `SCR-020` (requires valid Supabase JWT with role=faculty).
2. Fetch schedules via `GET /api/v1/schedules/me` (returns teaching schedules).
3. Render teaching schedule grouped by `day_of_week`, sorted by `start_time` ASC.
4. Pull-to-refresh to reload schedule data.

## Optional Detail Flow
1. Select schedule item from list.
2. Call `GET /api/v1/schedules/{id}` for detailed context (full schedule payload with faculty name, room name).
3. Optionally load roster via `GET /api/v1/schedules/{id}/students` in class detail views (faculty sees full roster, enrolled students see classmates).

## Auth Error Handling
- If JWT is expired/invalid, redirect to login screen.
- If 403 (forbidden), show appropriate error message.
