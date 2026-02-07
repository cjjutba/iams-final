# API Boundary Notes

## Owned by MOD-03
- `POST /face/register`
- `POST /face/recognize`
- `GET /face/status`

## Related but Owned by Other Module
- `POST /face/process` is owned by `MOD-04` (Edge Device Capture and Ingestion).

## Coordination Rule
Changes to `POST /face/process` payload that affect recognition extraction must be reflected in MOD-03 integration docs and tests.
