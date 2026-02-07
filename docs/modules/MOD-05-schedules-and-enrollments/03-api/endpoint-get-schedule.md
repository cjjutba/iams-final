# Endpoint Contract: GET /schedules/{id}

## Function Mapping
- `FUN-05-02`

## Purpose
Return one schedule by ID.

## Path Parameter
- `id` (UUID)

## Success Response
```json
{
  "success": true,
  "data": {}
}
```

## Error Cases
- `401`: missing/invalid token
- `404`: schedule not found
- `500`: server error
