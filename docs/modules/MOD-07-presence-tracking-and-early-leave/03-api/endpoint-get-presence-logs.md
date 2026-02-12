# Endpoint Contract: GET /presence/{attendance_id}/logs

## Function Mapping
- `FUN-07-06`

## Auth Requirement
- **Required:** Yes (Supabase JWT)
- **Role:** faculty or admin
- **Header:** `Authorization: Bearer <token>`

## Path Parameters
| Parameter | Type | Required | Description |
|---|---|---|---|
| `attendance_id` | UUID | Yes | The attendance record to retrieve presence logs for |

## Success Response
```json
{
  "success": true,
  "data": {
    "logs": [
      {
        "id": "uuid",
        "attendance_id": "uuid",
        "scan_number": 1,
        "detected": true,
        "scanned_at": "2026-02-12T08:05:00+08:00"
      },
      {
        "id": "uuid",
        "attendance_id": "uuid",
        "scan_number": 2,
        "detected": true,
        "scanned_at": "2026-02-12T08:06:00+08:00"
      },
      {
        "id": "uuid",
        "attendance_id": "uuid",
        "scan_number": 3,
        "detected": false,
        "scanned_at": "2026-02-12T08:07:00+08:00"
      }
    ]
  },
  "message": "Presence logs retrieved successfully"
}
```

## Timezone Note
All `scanned_at` timestamps are TIMESTAMPTZ and include timezone offset (e.g., `+08:00` for Asia/Manila).

## Error Cases
| Status | Code | Scenario |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Invalid attendance_id format |
| 401 | `UNAUTHORIZED` | Missing or invalid JWT |
| 403 | `FORBIDDEN` | Student role attempting access |
| 404 | `NOT_FOUND` | Attendance record not found |

## Notes
- Returns empty `logs` array (not 404) when attendance record exists but has no presence logs yet.
- Logs are sorted by `scan_number` ascending.
