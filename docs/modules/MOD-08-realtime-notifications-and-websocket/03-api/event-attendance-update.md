# Event Contract: attendance_update

## Function Mapping
- `FUN-08-02`

## Trigger
Attendance status change produced by attendance logic.

## Envelope
```json
{
  "type": "attendance_update",
  "data": {
    "student_id": "uuid",
    "status": "present",
    "timestamp": "2024-01-15T08:05:00Z"
  }
}
```

## Required Fields
| Field | Type | Required | Notes |
|---|---|---|---|
| `data.student_id` | UUID/string | Yes | Target student reference |
| `data.status` | string | Yes | Attendance status |
| `data.timestamp` | ISO datetime | Yes | Event time |

## Consumers
- `SCR-021` FacultyLiveAttendanceScreen
- `SCR-029` FacultyNotificationsScreen
- Optional student notifications if routed by backend policy
