# Event Contract: session_end

## Function Mapping
- `FUN-08-04`

## Trigger
Class session finalization for schedule/date context.

## Envelope
```json
{
  "type": "session_end",
  "data": {
    "schedule_id": "uuid",
    "summary": {
      "present": 28,
      "late": 1,
      "early_leave": 1,
      "absent": 0
    }
  }
}
```

## Required Fields
| Field | Type | Required | Notes |
|---|---|---|---|
| `data.schedule_id` | UUID/string | Yes | Session schedule reference |
| `data.summary` | object | Yes | Aggregated attendance counts |

## Summary Object Fields
- `present`
- `late`
- `early_leave`
- `absent`

## Consumers
- `SCR-021` FacultyLiveAttendanceScreen
- `SCR-018` StudentNotificationsScreen
- `SCR-029` FacultyNotificationsScreen
