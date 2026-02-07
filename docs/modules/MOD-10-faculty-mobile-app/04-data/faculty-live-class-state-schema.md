# Faculty Live-Class State Schema

## Live Session Shape (Conceptual)
```json
{
  "schedule_id": "uuid",
  "session_active": true,
  "started_at": "08:00:00",
  "current_scan": 15,
  "students": [
    {
      "id": "uuid",
      "name": "Juan Dela Cruz",
      "status": "present",
      "last_seen": "08:45:00",
      "consecutive_misses": 0
    }
  ]
}
```

## Derived UI Fields
- `present_count`
- `late_count`
- `absent_count`
- `early_leave_count`
- `is_session_active`

## Rules
- Derived counts should update when websocket events arrive.
- `session_active=false` must trigger inactive-session UI state.
