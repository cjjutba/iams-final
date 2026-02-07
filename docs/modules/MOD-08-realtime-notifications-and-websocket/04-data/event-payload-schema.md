# Event Payload Schema

## Standard Envelope
```json
{
  "type": "string",
  "data": {}
}
```

## attendance_update
```json
{
  "type": "attendance_update",
  "data": {
    "student_id": "uuid",
    "status": "present|late|absent|early_leave",
    "timestamp": "ISO-8601 datetime"
  }
}
```

## early_leave
```json
{
  "type": "early_leave",
  "data": {
    "student_id": "uuid",
    "student_name": "string (optional)",
    "schedule_id": "uuid",
    "detected_at": "ISO-8601 datetime",
    "consecutive_misses": "integer (optional)"
  }
}
```

## session_end
```json
{
  "type": "session_end",
  "data": {
    "schedule_id": "uuid",
    "summary": {
      "present": "integer",
      "late": "integer",
      "early_leave": "integer",
      "absent": "integer"
    }
  }
}
```

## Validation Rules
- Unknown `type` values are rejected in MVP.
- Required fields cannot be null.
- Datetime fields must be valid ISO-8601 strings.
