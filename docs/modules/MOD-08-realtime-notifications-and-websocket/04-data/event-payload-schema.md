# Event Payload Schema

## Standard Envelope
```json
{
  "type": "string",
  "data": {}
}
```

Note: This is the WebSocket message envelope. Not to be confused with the HTTP response envelope (`{ "success": true, "data": {}, "message": "" }`).

## Timezone Note
All datetime fields use ISO-8601 format with timezone offset based on `TIMEZONE` env var (default: Asia/Manila, +08:00).

---

## attendance_update
```json
{
  "type": "attendance_update",
  "data": {
    "student_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "schedule_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "status": "present",
    "timestamp": "2026-02-12T08:05:00+08:00"
  }
}
```

**Required fields:** `student_id` (UUID), `schedule_id` (UUID), `status` (string: `present|late|absent|early_leave`), `timestamp` (ISO-8601 with offset).

**Optional fields:** `student_name` (string), `student_id_number` (string).

---

## early_leave
```json
{
  "type": "early_leave",
  "data": {
    "student_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "student_name": "Juan Dela Cruz",
    "schedule_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "detected_at": "2026-02-12T09:30:00+08:00",
    "consecutive_misses": 3
  }
}
```

**Required fields:** `student_id` (UUID), `schedule_id` (UUID), `detected_at` (ISO-8601 with offset).

**Optional fields:** `student_name` (string), `consecutive_misses` (integer), `student_id_number` (string).

---

## session_end
```json
{
  "type": "session_end",
  "data": {
    "schedule_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "date": "2026-02-12",
    "summary": {
      "present": 28,
      "late": 1,
      "early_leave": 1,
      "absent": 0
    }
  }
}
```

**Required fields:** `schedule_id` (UUID), `summary` (object with `present`, `late`, `early_leave`, `absent` integer counts).

**Optional fields:** `date` (DATE ISO-8601), `subject_name` (string).

---

## Validation Rules
- Unknown `type` values are rejected in MVP.
- Required fields cannot be null.
- Datetime fields must be valid ISO-8601 strings with timezone offset.
- Status values must be one of: `present`, `late`, `absent`, `early_leave`.
- Summary count fields must be non-negative integers.
- Event payloads are additive-only: new optional fields OK, never remove required fields.
