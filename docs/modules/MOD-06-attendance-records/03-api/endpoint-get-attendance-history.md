# Endpoint Contract: GET /attendance?schedule_id=uuid&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD

## Function Mapping
- `FUN-06-04`

## Success Response
```json
{
  "success": true,
  "data": [],
  "pagination": {}
}
```

## Error Cases
- `400`: invalid filters
- `401`: missing/invalid token
- `403`: unauthorized role
- `404`: schedule not found (policy-dependent)
