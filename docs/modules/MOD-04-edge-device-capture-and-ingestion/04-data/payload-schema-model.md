# Payload Schema Model

## Outbound Payload Fields
| Field | Type | Required | Description |
|---|---|---|---|
| room_id | string UUID | yes | Room/session identifier |
| timestamp | ISO 8601 string | yes | Capture time |
| faces | array | yes | One or more face objects |
| faces[].image | base64 string | yes | JPEG payload (~112x112 crop at 70% quality) |
| faces[].bbox | [x, y, w, h] | no | Optional bounding box metadata |

## Validation Rules
- `faces` cannot be empty.
- `image` must be base64-encodable JPEG bytes.
- `timestamp` must be valid ISO 8601 format.

## Auth Header
Every outbound request must include:
```
X-API-Key: <value from EDGE_API_KEY env var>
```

## Crop Size Note
Edge crops faces at ~112x112 (detection output size from MediaPipe/OpenCV). Backend handles resize to 160x160 for FaceNet model input. The `image` field can contain any crop size; backend resizes as needed.
