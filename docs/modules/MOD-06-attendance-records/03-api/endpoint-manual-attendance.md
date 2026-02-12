# Endpoint Contract: POST /attendance/manual

## Function Mapping
- `FUN-06-05`

## Auth
- **Required:** Supabase JWT (`Authorization: Bearer <token>`)
- **Role:** Faculty or admin only
- **401:** Missing or invalid JWT
- **403:** Student role

## Request Body
```json
{
  "student_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "schedule_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "date": "2026-02-12",
  "status": "present",
  "remarks": "System was down during class period"
}
```

## Field Details
| Field | Type | Required | Constraints |
|---|---|---|---|
| student_id | UUID | Yes | FK → users.id (must be student role) |
| schedule_id | UUID | Yes | FK → schedules.id |
| date | YYYY-MM-DD | Yes | Date of attendance record |
| status | string | Yes | One of: `present`, `late`, `absent`, `early_leave` |
| remarks | string | Yes | Audit trail reason for manual entry |

## Success Response
```json
{
  "success": true,
  "data": {
    "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "student_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "schedule_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "date": "2026-02-12",
    "status": "present",
    "remarks": "System was down during class period",
    "updated_by": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "updated_at": "2026-02-12T14:30:00+08:00"
  },
  "message": "Attendance updated manually"
}
```

## Notes
- Upserts on `(student_id, schedule_id, date)` — creates if not exists, updates if exists.
- `updated_by` is automatically set to JWT sub (user ID of faculty/admin making the change).
- `updated_at` is automatically set to current timestamp.
- `remarks` is required for audit trail compliance.

## Error Cases
| Status | Code | Scenario |
|---|---|---|
| 401 | UNAUTHORIZED | Missing or invalid JWT |
| 403 | FORBIDDEN | Student role attempting manual entry |
| 404 | NOT_FOUND | student_id or schedule_id not found |
| 422 | VALIDATION_ERROR | Invalid status value, missing remarks, or invalid payload |
