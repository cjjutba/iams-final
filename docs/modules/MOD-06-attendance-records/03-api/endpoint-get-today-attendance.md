# Endpoint Contract: GET /attendance/today?schedule_id=uuid

## Function Mapping
- `FUN-06-02`

## Auth
- **Required:** Supabase JWT (`Authorization: Bearer <token>`)
- **Role:** Faculty or admin only
- **401:** Missing or invalid JWT
- **403:** Student role

## Success Response
```json
{
  "success": true,
  "data": {
    "schedule": {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "subject_name": "CPE 301",
      "room_name": "Room 301",
      "faculty_name": "Dr. Santos"
    },
    "records": [
      {
        "student_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "student_name": "Juan Dela Cruz",
        "student_id_number": "21-A-012345",
        "status": "present",
        "check_in_time": "2026-02-12T08:05:00+08:00",
        "presence_score": 95.5
      }
    ],
    "summary": {
      "total": 30,
      "present": 28,
      "late": 1,
      "absent": 1,
      "early_leave": 0
    }
  },
  "message": ""
}
```

## Query Parameters
| Param | Type | Required | Description |
|---|---|---|---|
| schedule_id | UUID | Yes | Schedule to retrieve today's attendance for |

## Notes
- "Today" is determined by the configured timezone (`TIMEZONE` env var, default: Asia/Manila).
- Summary includes all 4 status counts: present, late, absent, early_leave.

## Error Cases
| Status | Code | Scenario |
|---|---|---|
| 400 | VALIDATION_ERROR | Missing or invalid schedule_id format |
| 401 | UNAUTHORIZED | Missing or invalid JWT |
| 403 | FORBIDDEN | Student role attempting access |
| 404 | NOT_FOUND | Schedule not found |
