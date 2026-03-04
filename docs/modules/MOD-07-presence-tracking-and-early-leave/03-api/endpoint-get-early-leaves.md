# Endpoint Contract: GET /presence/early-leaves?schedule_id=uuid&date=YYYY-MM-DD

## Function Mapping
- `FUN-07-06`

## Auth Requirement
- **Required:** Yes (Supabase JWT)
- **Role:** faculty or admin
- **Header:** `Authorization: Bearer <token>`

## Query Parameters
| Parameter | Type | Required | Description |
|---|---|---|---|
| `schedule_id` | UUID | Yes | The schedule to filter early-leave events for |
| `date` | YYYY-MM-DD | Yes | The date to filter events for (in configured `TIMEZONE`) |

## Success Response
```json
{
  "success": true,
  "data": {
    "events": [
      {
        "id": "uuid",
        "attendance_id": "uuid",
        "schedule_id": "uuid",
        "student_id": "uuid",
        "student_name": "Juan Dela Cruz",
        "student_id_number": "21-A-012345",
        "flagged_at": "2026-02-12T09:30:00+08:00",
        "consecutive_misses": 3
      }
    ]
  },
  "message": "Early-leave events retrieved successfully"
}
```

## Timezone Note
- The `date` query parameter is interpreted in the configured `TIMEZONE` (default: Asia/Manila, +08:00).
- `flagged_at` timestamps are TIMESTAMPTZ and include timezone offset.

## Error Cases
| Status | Code | Scenario |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Invalid schedule_id or date format |
| 401 | `UNAUTHORIZED` | Missing or invalid JWT |
| 403 | `FORBIDDEN` | Student role attempting access |
| 404 | `NOT_FOUND` | Schedule not found |

## Notes
- Returns empty `events` array (not 404) when schedule exists but has no early-leave events for the given date.
- Events are sorted by `flagged_at` ascending.
