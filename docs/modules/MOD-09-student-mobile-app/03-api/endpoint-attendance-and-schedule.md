# Endpoint Contract: Attendance and Schedule

## Scope
Endpoints that power student home, schedule, and history views.

## Endpoints
| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /schedules/me` | Post-auth (JWT) | Student schedule list |
| `GET /attendance/me?start_date=...&end_date=...` | Post-auth (JWT) | Student attendance history |
| `GET /attendance/today?schedule_id=uuid` | Post-auth (JWT) | Per-class today attendance context |

**All endpoints require `Authorization: Bearer <token>` header.**

## Schedule Request
```
GET /api/v1/schedules/me
Authorization: Bearer <access_token>
```

### Schedule Response (Example)
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "subject_name": "CPE 301",
      "room_name": "Room 301",
      "day_of_week": "Monday",
      "start_time": "07:00:00",
      "end_time": "10:00:00",
      "faculty_name": "Prof. Faculty"
    }
  ]
}
```

## Attendance History Request
```
GET /api/v1/attendance/me?start_date=2026-02-01&end_date=2026-02-12
Authorization: Bearer <access_token>
```

### Attendance History Response (Example)
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "schedule_id": "uuid",
      "subject_name": "CPE 301",
      "attendance_date": "2026-02-12",
      "status": "present",
      "check_in_time": "2026-02-12T07:02:15+08:00",
      "presence_score": 95.0
    }
  ]
}
```

## Timezone Note
All timestamps use ISO-8601 with +08:00 offset (Asia/Manila). Date filter parameters use `YYYY-MM-DD` format.

## Client Behavior
1. Fetch schedule and attendance in parallel when appropriate.
2. Render loading/empty/error states per screen.
3. Preserve date-filter query consistency between UI and API.
4. Access response fields using snake_case (e.g., `subject_name`, `start_time`, `room_name`).
5. On 401: attempt refresh, fallback to login.

## Screens
- `SCR-011` StudentHomeScreen
- `SCR-012` StudentScheduleScreen
- `SCR-013` StudentAttendanceHistoryScreen
- `SCR-014` StudentAttendanceDetailScreen
