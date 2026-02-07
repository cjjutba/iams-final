# API Boundary Notes

## Ownership Boundaries
- `MOD-06` owns attendance computation and state transitions.
- `MOD-07` owns presence scans and early-leave detection.
- `MOD-08` owns realtime transport and event fanout.

## Input Contracts Into MOD-08
- Attendance update payloads from attendance flow.
- Early-leave payloads from presence flow.
- Session summary payloads from session-finalization flow.

## Output Contracts From MOD-08
- WebSocket messages to connected mobile clients.
- Optional delivery logs for observability.

## Cross-Module Coordination
Any upstream payload shape change must update:
1. `03-api/event-*.md` files
2. `04-data/event-payload-schema.md`
3. `05-screens/state-matrix.md` if UI states are impacted
