# Payload Schema Model

## Outbound Payload Fields
| Field | Type | Required | Description |
|---|---|---|---|
| room_id | string UUID | yes | room/session identifier |
| timestamp | ISO 8601 string | yes | capture time |
| faces | array | yes | one or more face objects |
| faces[].image | base64 string | yes | JPEG payload |
| faces[].bbox | [x,y,w,h] | no | optional tracking metadata |

## Validation Rules
- `faces` cannot be empty.
- `image` must be base64-encodable JPEG bytes.
- `timestamp` must be valid ISO format.
