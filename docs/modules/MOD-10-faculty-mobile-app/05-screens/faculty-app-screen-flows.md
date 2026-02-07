# Faculty App Screen Flows

## Auth Flow
1. Faculty enters via `SCR-005` FacultyLoginScreen.
2. Optional password recovery through `SCR-006`.
3. Successful auth routes to `SCR-019` FacultyHomeScreen.

## Schedule and Live Class Flow
1. `SCR-019` shows current-day class overview and active class status.
2. `SCR-020` displays full faculty schedule list.
3. Selecting/entering active class opens `SCR-021` live attendance.

## Class Operations Flow
1. From `SCR-021`, open `SCR-022` class detail summary.
2. Drill into `SCR-023` student detail/presence logs.
3. Use `SCR-024` for manual attendance actions.
4. View alert list in `SCR-025`.
5. View summary/report context in `SCR-026`.

## Profile and Notification Flow
1. View profile in `SCR-027`.
2. Edit profile in `SCR-028` and return to profile.
3. Open notification feed in `SCR-029` for realtime events.

## Realtime Recovery Flow
1. Live/notification screen detects websocket disconnect.
2. UI enters reconnecting state.
3. Client retries connection and resumes stream.
4. Screen updates continue without app restart.
