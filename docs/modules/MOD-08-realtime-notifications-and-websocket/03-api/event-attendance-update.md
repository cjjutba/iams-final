# Event Contract: attendance_update

## Function Mapping
- `FUN-08-02` (system-internal, no JWT)

## Caller Context
- Called by: `attendance_service.py` (MOD-06) on attendance status transitions.
- Call pattern: Synchronous in-line call after status persistence.

## Trigger
Attendance status change produced by attendance logic (MOD-06).

## Envelope
```json
{
  "type": "attendance_update",
  "data": {
    "student_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "schedule_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "status": "present",
    "timestamp": "2026-02-12T08:05:00+08:00"
  }
}
```

## Required Fields
| Field | Type | Required | Notes |
|---|---|---|---|
| `data.student_id` | UUID | Yes | Target student reference |
| `data.schedule_id` | UUID | Yes | Schedule context for the attendance record |
| `data.status` | string | Yes | Attendance status: `present`, `late`, `absent`, `early_leave` |
| `data.timestamp` | ISO-8601 datetime | Yes | Event time with timezone offset (`+08:00`) |

## Optional Fields
| Field | Type | Notes |
|---|---|---|
| `data.student_name` | string | Display name for UI convenience |
| `data.student_id_number` | string | Student ID number (e.g., `21-A-012345`) |

## Timezone Note
`timestamp` field uses ISO-8601 format with timezone offset based on `TIMEZONE` env var (default: Asia/Manila, +08:00).

## Consumers
- `SCR-021` FacultyLiveAttendanceScreen — updates roster status row
- `SCR-029` FacultyNotificationsScreen — adds feed item
- `SCR-018` StudentNotificationsScreen — student receives own attendance update (if routed)
