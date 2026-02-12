# Event Contract: early_leave

## Function Mapping
- `FUN-08-03` (system-internal, no JWT)

## Caller Context
- Called by: `presence_service.py` (MOD-07) when early-leave threshold is reached (3 consecutive misses).
- Call pattern: Synchronous in-line call after early-leave event creation and attendance status update.

## Trigger
Presence logic flags early-leave threshold for a student (MOD-07).

## Envelope
```json
{
  "type": "early_leave",
  "data": {
    "student_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "student_name": "Juan Dela Cruz",
    "schedule_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "detected_at": "2026-02-12T09:30:00+08:00",
    "consecutive_misses": 3
  }
}
```

## Required Fields
| Field | Type | Required | Notes |
|---|---|---|---|
| `data.student_id` | UUID | Yes | Student reference |
| `data.schedule_id` | UUID | Yes | Session schedule reference |
| `data.detected_at` | ISO-8601 datetime | Yes | Detection timestamp with timezone offset (`+08:00`) |

## Optional Fields
| Field | Type | Notes |
|---|---|---|
| `data.student_name` | string | Display name for alert UI |
| `data.consecutive_misses` | integer | Miss count at detection time (default: 3) |
| `data.student_id_number` | string | Student ID number (e.g., `21-A-02177`) |

## Timezone Note
`detected_at` field uses ISO-8601 format with timezone offset based on `TIMEZONE` env var (default: Asia/Manila, +08:00).

## Dedup Rule
MOD-07 is responsible for dedup (one early-leave event per `attendance_id`). MOD-08 should not re-emit if called twice for the same event context.

## Consumers
- `SCR-021` FacultyLiveAttendanceScreen — shows alert indicator and list update
- `SCR-025` FacultyEarlyLeaveAlertsScreen — dedicated early-leave alert feed
- `SCR-029` FacultyNotificationsScreen — adds alert feed item
