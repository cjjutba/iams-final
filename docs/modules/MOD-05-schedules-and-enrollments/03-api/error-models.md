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

## Schedule-Related Error Codes
| Code | Description |
|---|---|
| `VALIDATION_ERROR` | Invalid payload, query params, or field values |
| `UNAUTHORIZED` | Missing or invalid Supabase JWT |
| `FORBIDDEN` | Caller lacks required role (e.g., non-admin on POST /schedules) |
| `NOT_FOUND` | Schedule not found by ID |
| `CONFLICT` | Constraint violation (e.g., duplicate enrollment) |
| `SERVER_ERROR` | Unexpected server error |

## Status Mapping
| Status | Error Code | Typical Schedule Scenario |
|---|---|---|
| 400 | `VALIDATION_ERROR` | invalid day_of_week, start_time >= end_time, invalid UUID format |
| 401 | `UNAUTHORIZED` | missing or invalid Supabase JWT bearer token |
| 403 | `FORBIDDEN` | non-admin caller on POST /schedules, unauthorized roster access |
| 404 | `NOT_FOUND` | schedule UUID not found in database |
| 409 | `CONFLICT` | duplicate enrollment constraint violation |
| 500 | `SERVER_ERROR` | unexpected server error |

## Error Scenarios by Function
| Function | Scenario | Status | Code |
|---|---|---|---|
| FUN-05-01 | invalid day filter (e.g., day=9) | 400 | `VALIDATION_ERROR` |
| FUN-05-01 | missing JWT | 401 | `UNAUTHORIZED` |
| FUN-05-02 | schedule not found | 404 | `NOT_FOUND` |
| FUN-05-02 | missing JWT | 401 | `UNAUTHORIZED` |
| FUN-05-03 | start_time >= end_time | 400 | `VALIDATION_ERROR` |
| FUN-05-03 | invalid faculty_id or room_id FK | 400 | `VALIDATION_ERROR` |
| FUN-05-03 | non-admin caller | 403 | `FORBIDDEN` |
| FUN-05-03 | missing JWT | 401 | `UNAUTHORIZED` |
| FUN-05-04 | unsupported role | 403 | `FORBIDDEN` |
| FUN-05-04 | missing JWT | 401 | `UNAUTHORIZED` |
| FUN-05-05 | schedule not found | 404 | `NOT_FOUND` |
| FUN-05-05 | not authorized to view roster | 403 | `FORBIDDEN` |
| FUN-05-05 | missing JWT | 401 | `UNAUTHORIZED` |
