# Event Contract: session_end

## Function Mapping
- `FUN-08-04` (system-internal, no JWT)

## Caller Context
- Called by: Session finalization logic (triggered when schedule end time is reached or session is manually closed).
- Call pattern: Called once per schedule/date session at session end.

## Trigger
Class session finalization for schedule/date context.

## Envelope
```json
{
  "type": "session_end",
  "data": {
    "schedule_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "date": "2026-02-12",
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
| `data.schedule_id` | UUID | Yes | Session schedule reference |
| `data.summary` | object | Yes | Aggregated attendance counts |

## Summary Object Fields
| Field | Type | Required | Notes |
|---|---|---|---|
| `summary.present` | integer | Yes | Count of students marked present |
| `summary.late` | integer | Yes | Count of students marked late |
| `summary.early_leave` | integer | Yes | Count of students flagged early leave |
| `summary.absent` | integer | Yes | Count of students marked absent |

## Optional Fields
| Field | Type | Notes |
|---|---|---|
| `data.date` | DATE (ISO-8601) | Session date in configured timezone (e.g., `2026-02-12`) |
| `data.subject_name` | string | Subject name for display convenience |

## Timezone Note
`date` field uses the configured `TIMEZONE` (default: Asia/Manila) for determining session date boundary.

## Idempotency
Session-end event should be emitted once per schedule/date session. Duplicate emission for the same schedule+date is prevented at the caller level.

## Consumers
- `SCR-021` FacultyLiveAttendanceScreen — shows summary and closes active state
- `SCR-018` StudentNotificationsScreen — adds summary event
- `SCR-029` FacultyNotificationsScreen — adds summary event
