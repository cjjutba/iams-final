# API Boundary Notes

## Owned by MOD-04
- `POST /face/process` caller behavior, payload formation, retry/queue handling.

## Related but Owned by Other Modules
- `POST /face/recognize` owned by `MOD-03`.
- Attendance and presence result handling owned by `MOD-06` and `MOD-07`.

## Coordination Rule
Payload schema changes in backend must be synchronized with edge sender and retry logic before deployment.
