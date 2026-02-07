# API Boundary Notes

## Owned by MOD-07
- Presence logs and early-leave query endpoints.
- Internal scan/miss/flag score behaviors.

## Related but Owned by Other Modules
- Attendance row creation/update in `MOD-06`.
- WebSocket event delivery in `MOD-08`.
- Recognition inputs from `MOD-03` and `MOD-04`.

## Coordination Rule
Changes to threshold/session behavior must be synchronized with attendance status updates and realtime alert payloads.
