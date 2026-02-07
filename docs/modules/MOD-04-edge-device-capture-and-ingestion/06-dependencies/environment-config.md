# Environment Configuration

## Required Variables (Edge Context)
- `EDGE_SERVER_URL`
- `ROOM_ID` (or equivalent runtime room/session identifier)
- camera config values (resolution/FPS)
- queue/retry config values (if configurable)

## Configuration Rules
- Backend URL must be reachable from edge network.
- Queue limits should be explicit and not unlimited.
- Missing critical config should fail fast.

## Validation Checklist
- Edge service starts with valid env.
- Payload target endpoint resolved correctly.
- Runtime logs include effective config summary (non-secret).
