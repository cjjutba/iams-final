# Agent Routing

## Recommended Agent Roles
- `websocket-specialist.md`: backend websocket endpoint, connection manager, fanout logic
- `websocket-mobile-specialist.md`: mobile websocket service and reconnect behavior
- `backend-core-specialist.md`: auth integration and service wiring

## Routing Rules
1. Use websocket specialist for `FUN-08-01` to `FUN-08-05` backend implementation.
2. Use mobile websocket specialist for screen/service integration.
3. Use backend core specialist when changes intersect auth or shared router patterns.

## Handoff Contract
Every agent handoff must include:
- Target `FUN-08-*` IDs
- Exact files touched
- Tests run and result summary
- Any docs updated in this module pack
