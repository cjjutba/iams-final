# Endpoint Contract: Early-Leave and Class Summary

## Scope
Endpoints for early-leave alerts, presence detail, and class summary/history context.

## Endpoints
| Endpoint | Method | Auth |
|---|---|---|
| `/presence/early-leaves?schedule_id=uuid&date=YYYY-MM-DD` | GET | Post-auth |
| `/presence/{attendance_id}/logs` | GET | Post-auth |
| `/attendance/today?schedule_id=uuid` | GET | Post-auth |
| `/attendance?schedule_id=uuid&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | GET | Post-auth |

## Early-Leave Response Example
**Request** (post-auth):
```
GET /api/v1/presence/early-leaves?schedule_id=uuid&date=2026-02-12
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "student_id": "uuid",
      "student_name": "Juan Dela Cruz",
      "detected_at": "2026-02-12T09:15:00+08:00",
      "consecutive_misses": 3,
      "schedule_id": "uuid"
    }
  ]
}
```

## Client Rules
1. Apply selected class/date filters before request.
2. Display clear empty state when no early-leave events exist.
3. Keep summary cards aligned with returned attendance totals.
4. All timestamps display in +08:00 timezone.
5. Date parameters use YYYY-MM-DD format.

## Screens
- `SCR-022` FacultyClassDetailScreen
- `SCR-023` FacultyStudentDetailScreen
- `SCR-025` FacultyAlertsScreen
- `SCR-026` FacultyReportsScreen
