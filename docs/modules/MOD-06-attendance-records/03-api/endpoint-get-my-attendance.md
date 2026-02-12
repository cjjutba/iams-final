# Endpoint Contract: GET /attendance/me?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD

## Function Mapping
- `FUN-06-03`

## Auth
- **Required:** Supabase JWT (`Authorization: Bearer <token>`)
- **Role:** Any authenticated user (role-scoped)
  - Student: sees own attendance records (JWT sub scoped)
  - Faculty: sees attendance for their assigned classes (faculty_id match)
- **401:** Missing or invalid JWT

## Success Response
```json
{
  "success": true,
  "data": [
    {
      "date": "2026-02-12",
      "schedule": {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "subject_name": "CPE 301",
        "room_name": "Room 301"
      },
      "status": "present",
      "check_in_time": "2026-02-12T08:05:00+08:00",
      "presence_score": 95.5
    }
  ],
  "message": ""
}
```

## Query Parameters
| Param | Type | Required | Description |
|---|---|---|---|
| start_date | YYYY-MM-DD | No | Start of date range filter (inclusive) |
| end_date | YYYY-MM-DD | No | End of date range filter (inclusive) |

## Notes
- Results sorted by date DESC.
- Date range filters are optional. If omitted, returns all available records.
- Dates interpreted in configured timezone (`TIMEZONE` env var, default: Asia/Manila).

## Error Cases
| Status | Code | Scenario |
|---|---|---|
| 401 | UNAUTHORIZED | Missing or invalid JWT |
| 422 | VALIDATION_ERROR | Invalid date range (start_date > end_date) |
