# Event Contract: early_leave

## Function Mapping
- `FUN-08-03`

## Trigger
Presence logic flags early-leave threshold for a student.

## Envelope
```json
{
  "type": "early_leave",
  "data": {
    "student_id": "uuid",
    "student_name": "Juan Dela Cruz",
    "schedule_id": "uuid",
    "detected_at": "2024-01-15T09:30:00Z"
  }
}
```

## Required Fields
| Field | Type | Required | Notes |
|---|---|---|---|
| `data.student_id` | UUID/string | Yes | Student reference |
| `data.schedule_id` | UUID/string | Yes | Session schedule reference |
| `data.detected_at` | ISO datetime | Yes | Detection timestamp |

## Optional Fields
- `data.student_name`
- `data.consecutive_misses`

## Consumers
- `SCR-021` FacultyLiveAttendanceScreen
- `SCR-025` FacultyEarlyLeaveAlertsScreen
- `SCR-029` FacultyNotificationsScreen
