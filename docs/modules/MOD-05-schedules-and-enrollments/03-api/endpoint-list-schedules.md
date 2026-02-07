# Endpoint Contract: GET /schedules?day=1

## Function Mapping
- `FUN-05-01`

## Purpose
List schedules using day/filter query.

## Request
Query params:
- `day` (example: 1)

## Success Response
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "subject_code": "CS101",
      "subject_name": "Programming 1",
      "faculty_name": "Dr. Santos",
      "room": "Room 301",
      "day_of_week": 1,
      "start_time": "08:00",
      "end_time": "10:00"
    }
  ]
}
```

## Error Cases
- `400`: invalid query filter
- `401`: missing/invalid token
- `500`: server error
