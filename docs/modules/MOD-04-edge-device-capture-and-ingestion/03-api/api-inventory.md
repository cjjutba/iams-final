# API Inventory

## Base
- Backend URL: configured via `EDGE_SERVER_URL`
- Primary contract endpoint: `POST /face/process`

## Endpoint List
| Method | Path | Function ID | Caller | Auth Required |
|---|---|---|---|---|
| POST | `/face/process` | FUN-04-03, FUN-04-04, FUN-04-05 | edge runtime | depends on deployment policy |

## Request Contract Summary
- `room_id`: string UUID
- `timestamp`: ISO 8601 string
- `faces[]`: list of face objects
- `faces[].image`: base64 JPEG
- `faces[].bbox`: optional [x, y, w, h]

## Response Contract Summary
- `data.processed`: count
- `data.matched[]`: recognized users + confidence
- `data.unmatched`: count
