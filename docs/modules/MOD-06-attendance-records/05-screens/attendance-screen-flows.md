# Attendance Screen Flows

## Student Attendance Flow
1. Open `SCR-011` for today's status snapshot.
2. Open `SCR-013` for historical records list.
3. Open `SCR-014` for detailed record view.

## Faculty Attendance Flow
1. Open `SCR-019` for class overview.
2. Open `SCR-021` for live attendance monitoring.
3. Use `SCR-024` to submit manual attendance entries.

## Data Fetch Sequence
- Today's view: `GET /attendance/today?schedule_id=...`
- Student history: `GET /attendance/me?...`
- Class history: `GET /attendance?...`
- Manual entry: `POST /attendance/manual`
- Live monitoring: `GET /attendance/live/{schedule_id}`
