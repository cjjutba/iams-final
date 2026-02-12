# Endpoint Contract: Schedule and Active Class

## Scope
Endpoints and rules used to show faculty schedule and resolve active class.

## Endpoints
| Endpoint | Method | Auth |
|---|---|---|
| `/schedules/me` | GET | Post-auth |
| `/schedules/{id}/students` | GET | Post-auth |

## Active Class Resolution
1. Load all faculty schedules for current day context.
2. Determine active class by comparing current time against schedule bounds using Asia/Manila timezone (+08:00).
3. If active, route to live attendance screen context.

## Schedule Response Example
**Request** (post-auth, JWT required):
```
GET /api/v1/schedules/me
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "subject_name": "CPE 301",
      "room_name": "Room 301",
      "day_of_week": "Monday",
      "start_time": "07:00:00+08:00",
      "end_time": "10:00:00+08:00",
      "faculty_id": "uuid"
    }
  ]
}
```

## Timezone Note
- Response fields use snake_case and +08:00 offset.
- Active class resolution must use Asia/Manila timezone.

## Screens
- `SCR-019` FacultyHomeScreen
- `SCR-020` FacultyScheduleScreen
- `SCR-021` FacultyLiveAttendanceScreen
