# Manual Attendance Payload Schema

## Request Shape
```json
{
  "student_id": "uuid",
  "schedule_id": "uuid",
  "date": "YYYY-MM-DD",
  "status": "present|late|absent|early_leave",
  "remarks": "optional text"
}
```

## Validation Rules
- `student_id`, `schedule_id`, `date`, and `status` are required.
- `status` must be one of allowed enum values.
- `remarks` is optional but should be trimmed and length-bounded.

## UI Rules
- Disable submit while request in progress.
- Show success/failure feedback and refresh target roster view after success.
