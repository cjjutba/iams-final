# Endpoint Contract: Live and Manual Attendance

## Scope
Endpoints powering live class monitoring and manual attendance actions.

## Endpoints
- `GET /attendance/live/{schedule_id}`
- `GET /attendance/today?schedule_id=uuid`
- `POST /attendance/manual`

## Manual Attendance Payload (Example)
```json
{
  "student_id": "uuid",
  "schedule_id": "uuid",
  "date": "2024-01-15",
  "status": "present",
  "remarks": "System was down"
}
```

## Client Rules
1. Manual action allowed only for faculty role.
2. After success, refresh live/today view data.
3. Handle 403 and validation errors with actionable feedback.

## Screens
- `SCR-021` FacultyLiveAttendanceScreen
- `SCR-024` FacultyManualEntryScreen
