# Manual Attendance Payload Schema

## Request Shape
```json
{
  "student_id": "uuid",
  "schedule_id": "uuid",
  "date": "2026-02-12",
  "status": "present",
  "remarks": "System was down"
}
```

## Auth Context
- **Auth:** Post-auth — requires `Authorization: Bearer <token>` header.
- **Endpoint:** `POST /attendance/manual`
- **Role restriction:** Faculty only (403 if student attempts).

## Validation Rules
- `student_id`, `schedule_id`, `date`, and `status` are required.
- `date` must use `YYYY-MM-DD` format.
- `status` must be one of allowed enum values: `present`, `late`, `absent`, `early_leave`.
- `remarks` is optional but should be trimmed and length-bounded.

## Response Envelope
**Success:**
```json
{ "success": true, "data": { ... }, "message": "Attendance updated" }
```

**Error** (no `details` array):
```json
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "..." } }
```

## UI Rules
- Disable submit while request in progress.
- Show success/failure feedback and refresh target roster view after success.
- Keep draft values on error for correction.
