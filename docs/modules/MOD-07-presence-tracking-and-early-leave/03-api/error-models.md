# Error Models

## Standard Error Shape
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```
Note: No `details` array — consistent with MOD-01 through MOD-06 error envelope.

## Error Codes
| Code | Description |
|---|---|
| `VALIDATION_ERROR` | Invalid input (attendance_id, schedule_id, date format) |
| `UNAUTHORIZED` | Missing or invalid Supabase JWT |
| `FORBIDDEN` | Insufficient role (e.g., student accessing faculty-only endpoint) |
| `NOT_FOUND` | Referenced attendance record or schedule does not exist |
| `THRESHOLD_CONFIG_ERROR` | Invalid threshold/interval configuration (system-internal) |
| `SERVER_ERROR` | Unexpected service error |

## Error Scenarios by Function
| Function | Status | Code | Scenario |
|---|---|---|---|
| FUN-07-06 (logs) | 400 | `VALIDATION_ERROR` | Invalid attendance_id format |
| FUN-07-06 (logs) | 401 | `UNAUTHORIZED` | Missing or invalid JWT |
| FUN-07-06 (logs) | 403 | `FORBIDDEN` | Student role attempting access |
| FUN-07-06 (logs) | 404 | `NOT_FOUND` | Attendance record not found |
| FUN-07-06 (early-leaves) | 400 | `VALIDATION_ERROR` | Invalid schedule_id or date format |
| FUN-07-06 (early-leaves) | 401 | `UNAUTHORIZED` | Missing or invalid JWT |
| FUN-07-06 (early-leaves) | 403 | `FORBIDDEN` | Student role attempting access |
| FUN-07-06 (early-leaves) | 404 | `NOT_FOUND` | Schedule not found |
| FUN-07-06 (any) | 401 | `UNAUTHORIZED` | Expired JWT |
| FUN-07-06 (any) | 500 | `SERVER_ERROR` | Unexpected service error |

## Status Mapping
| Status | Typical Presence Scenario |
|---|---|
| 400 | Invalid attendance_id/date/schedule filters |
| 401 | Missing, invalid, or expired JWT |
| 403 | Unauthorized role (student on faculty-only endpoint) |
| 404 | Attendance/schedule context not found |
| 500 | Unexpected service error |
