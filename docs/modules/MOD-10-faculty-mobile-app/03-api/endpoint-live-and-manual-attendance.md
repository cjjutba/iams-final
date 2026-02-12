# Endpoint Contract: Live and Manual Attendance

## Scope
Endpoints powering live class monitoring and manual attendance actions.

## Endpoints
| Endpoint | Method | Auth |
|---|---|---|
| `/attendance/live/{schedule_id}` | GET | Post-auth |
| `/attendance/today?schedule_id=uuid` | GET | Post-auth |
| `/attendance/manual` | POST | Post-auth |

## Live Attendance Response Example
**Request** (post-auth):
```
GET /api/v1/attendance/live/uuid
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "data": {
    "schedule_id": "uuid",
    "session_active": true,
    "students": [
      {
        "student_id": "uuid",
        "student_name": "Juan Dela Cruz",
        "status": "present",
        "last_seen": "2026-02-12T08:45:00+08:00"
      }
    ]
  }
}
```

## Manual Attendance Payload Example
**Request** (post-auth):
```json
POST /api/v1/attendance/manual
Authorization: Bearer <token>

{
  "student_id": "uuid",
  "schedule_id": "uuid",
  "date": "2026-02-12",
  "status": "present",
  "remarks": "System was down"
}
```

**Success Response:**
```json
{
  "success": true,
  "data": { ... },
  "message": "Attendance updated"
}
```

## Client Rules
1. Manual action allowed only for faculty role.
2. After success, refresh live/today view data.
3. Handle 403 and validation errors with actionable feedback.
4. Status enum: `present`, `late`, `absent`, `early_leave`.
5. Date format: `YYYY-MM-DD`.

## Screens
- `SCR-021` FacultyLiveAttendanceScreen
- `SCR-024` FacultyManualEntryScreen
