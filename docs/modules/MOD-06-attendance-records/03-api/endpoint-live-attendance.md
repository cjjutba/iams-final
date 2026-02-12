# Endpoint Contract: GET /attendance/live/{schedule_id}

## Function Mapping
- `FUN-06-06`

## Auth
- **Required:** Supabase JWT (`Authorization: Bearer <token>`)
- **Role:** Faculty or admin only
- **401:** Missing or invalid JWT
- **403:** Student role

## Success Response (Active Session)
```json
{
  "success": true,
  "data": {
    "schedule": {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "subject_name": "CPE 301",
      "room_name": "Room 301"
    },
    "session_active": true,
    "started_at": "2026-02-12T08:00:00+08:00",
    "current_scan": 15,
    "students": [
      {
        "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "name": "Juan Dela Cruz",
        "student_id_number": "21-A-02177",
        "status": "present",
        "last_seen": "2026-02-12T08:45:00+08:00",
        "consecutive_misses": 0
      }
    ]
  },
  "message": ""
}
```

## Success Response (No Active Session)
```json
{
  "success": true,
  "data": {
    "session_active": false
  },
  "message": "No active session"
}
```

## Path Parameters
| Param | Type | Required | Description |
|---|---|---|---|
| schedule_id | UUID | Yes | Schedule to monitor live attendance for |

## Notes
- Active session is determined by: `is_active=true` AND `day_of_week` matches today AND current time within `[start_time, end_time]` in configured timezone.
- `consecutive_misses` tracks missed 60-second scans (MOD-07 presence tracking). 3 consecutive misses triggers early-leave detection.
- `current_scan` indicates the scan cycle number since session start.
- Timestamps use configured timezone (`TIMEZONE` env var, default: Asia/Manila).

## Error Cases
| Status | Code | Scenario |
|---|---|---|
| 401 | UNAUTHORIZED | Missing or invalid JWT |
| 403 | FORBIDDEN | Student role attempting access |
| 404 | NOT_FOUND | Schedule not found |
