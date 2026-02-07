# API Boundary Notes

## Owned by MOD-06
- Attendance endpoint family and attendance-record lifecycle behavior.

## Related but Owned by Other Modules
- Recognition ingestion flows in `MOD-03` and `MOD-04` supply events for marking.
- Presence logs and early-leave events are owned by `MOD-07`.
- Realtime event delivery is owned by `MOD-08`.

## Coordination Rule
Any attendance status or payload change must be synchronized with presence and websocket event contracts.
