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

## Attendance-Related Codes
| Code | Description |
|---|---|
| VALIDATION_ERROR | Invalid payload, date format, or status value |
| UNAUTHORIZED | Missing or invalid Supabase JWT |
| FORBIDDEN | Insufficient role (e.g., student accessing faculty-only endpoint) |
| NOT_FOUND | Referenced schedule, student, or attendance record not found |
| CONFLICT | Conflict in manual update/upsert policy |
| SERVER_ERROR | Unexpected server error |

## Status Mapping
| Status | Error Code | Typical Attendance Scenario |
|---|---|---|
| 400 | VALIDATION_ERROR | Invalid date/status/payload format |
| 401 | UNAUTHORIZED | Missing or invalid Supabase JWT |
| 403 | FORBIDDEN | Student role accessing faculty-only endpoint, or faculty accessing unassigned schedule |
| 404 | NOT_FOUND | Attendance target, schedule, or student not found |
| 409 | CONFLICT | Conflict in manual update/upsert policy |
| 422 | VALIDATION_ERROR | Invalid date range (start_date > end_date), invalid status value, missing required remarks |
| 500 | SERVER_ERROR | Unexpected server error |

## Error Scenarios by Function
| Function | Status | Code | Scenario |
|---|---|---|---|
| FUN-06-02 | 400 | VALIDATION_ERROR | Missing or invalid schedule_id |
| FUN-06-02 | 401 | UNAUTHORIZED | Missing JWT |
| FUN-06-02 | 403 | FORBIDDEN | Student role |
| FUN-06-02 | 404 | NOT_FOUND | Schedule not found |
| FUN-06-03 | 401 | UNAUTHORIZED | Missing JWT |
| FUN-06-03 | 422 | VALIDATION_ERROR | start_date > end_date |
| FUN-06-04 | 401 | UNAUTHORIZED | Missing JWT |
| FUN-06-04 | 403 | FORBIDDEN | Student role or unassigned faculty |
| FUN-06-04 | 404 | NOT_FOUND | Schedule not found |
| FUN-06-05 | 401 | UNAUTHORIZED | Missing JWT |
| FUN-06-05 | 403 | FORBIDDEN | Student role |
| FUN-06-05 | 404 | NOT_FOUND | student_id or schedule_id not found |
| FUN-06-05 | 422 | VALIDATION_ERROR | Invalid status or missing remarks |
| FUN-06-06 | 401 | UNAUTHORIZED | Missing JWT |
| FUN-06-06 | 403 | FORBIDDEN | Student role |
| FUN-06-06 | 404 | NOT_FOUND | Schedule not found |
