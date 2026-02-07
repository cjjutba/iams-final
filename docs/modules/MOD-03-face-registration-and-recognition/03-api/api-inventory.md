# API Inventory

## Base
- Base URL: `http://localhost:8000/api/v1` (development)
- Auth Header (where protected): `Authorization: Bearer <token>`

## Endpoint List
| Method | Path | Function ID | Caller | Auth Required |
|---|---|---|---|---|
| POST | `/face/register` | FUN-03-01, FUN-03-02, FUN-03-03 | student face registration flow | Yes |
| POST | `/face/recognize` | FUN-03-04 | edge/recognition caller | depends on deployment policy |
| GET | `/face/status` | FUN-03-05 | app registration status checks | Yes |

## Related Boundary Endpoint (Owned by MOD-04)
- `POST /face/process` (edge batch processing contract)

## Response Envelope
Success:
```json
{
  "success": true,
  "data": {}
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
