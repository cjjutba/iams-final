# Endpoint Contract: POST /schedules

## Function Mapping
- `FUN-05-03`

## Purpose
Create new schedule (admin flow).

## Request
```json
{
  "subject_code": "CS101",
  "subject_name": "Programming 1",
  "faculty_id": "uuid",
  "room_id": "uuid",
  "day_of_week": 1,
  "start_time": "08:00",
  "end_time": "10:00"
}
```

## Success Response
```json
{
  "success": true,
  "data": {}
}
```

## Error Cases
- `400`: invalid payload/time values/references
- `401`: missing/invalid token
- `403`: non-admin caller
- `500`: server error
