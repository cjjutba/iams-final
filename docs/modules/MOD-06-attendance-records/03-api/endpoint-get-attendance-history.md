# Endpoint Contract: GET /attendance?schedule_id=uuid&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD

## Function Mapping
- `FUN-06-04`

## Auth
- **Required:** Supabase JWT (`Authorization: Bearer <token>`)
- **Role:** Faculty or admin only
  - Faculty: restricted to own assigned schedules (faculty_id match). Returns 403 for unassigned schedule.
  - Admin: unrestricted access to any schedule.
- **401:** Missing or invalid JWT
- **403:** Student role, or faculty accessing unassigned schedule

## Success Response
```json
{
  "success": true,
  "data": [
    {
      "date": "2026-02-12",
      "student_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "student_name": "Juan Dela Cruz",
      "student_id_number": "21-A-02177",
      "status": "present",
      "check_in_time": "2026-02-12T08:05:00+08:00",
      "presence_score": 95.5,
      "remarks": null
    }
  ],
  "message": ""
}
```

## Query Parameters
| Param | Type | Required | Description |
|---|---|---|---|
| schedule_id | UUID | Yes | Schedule to retrieve attendance history for |
| start_date | YYYY-MM-DD | No | Start of date range filter (inclusive) |
| end_date | YYYY-MM-DD | No | End of date range filter (inclusive) |

## Notes
- Results sorted by date DESC.
- Missing date filters return all available records for the schedule.
- Dates interpreted in configured timezone (`TIMEZONE` env var, default: Asia/Manila).

## Error Cases
| Status | Code | Scenario |
|---|---|---|
| 400 | VALIDATION_ERROR | Missing or invalid schedule_id format |
| 401 | UNAUTHORIZED | Missing or invalid JWT |
| 403 | FORBIDDEN | Student role, or faculty accessing unassigned schedule |
| 404 | NOT_FOUND | Schedule not found |
| 422 | VALIDATION_ERROR | Invalid date range (start_date > end_date) |
