# API Inventory

## Base
- Base URL: `http://localhost:8000/api/v1` (development)

## Auth Context
- **Student-facing endpoints** (`POST /face/register`, `GET /face/status`): Protected by Supabase JWT middleware from MOD-01. Header: `Authorization: Bearer <supabase_jwt>`. Backend verifies JWT signature, checks `is_active = true` and `email_confirmed_at IS NOT NULL`.
- **Edge-facing endpoint** (`POST /face/recognize`): Protected by shared API key. Header: `X-API-Key: <edge_api_key>`. Backend validates against `EDGE_API_KEY` env variable.

## Endpoint List
| Method | Path | Function ID | Caller | Auth |
|---|---|---|---|---|
| POST | `/face/register` | FUN-03-01, FUN-03-02, FUN-03-03 | student face registration flow | Supabase JWT |
| POST | `/face/recognize` | FUN-03-04 | edge/recognition caller (RPi) | API key (`X-API-Key`) |
| GET | `/face/status` | FUN-03-05 | app registration status checks | Supabase JWT |

## Related Boundary Endpoint (Owned by MOD-04)
- `POST /face/process` (edge batch processing contract) — also uses API key auth

## Response Envelope
Success:
```json
{
  "success": true,
  "data": {},
  "message": ""
}
```

Error:
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```
