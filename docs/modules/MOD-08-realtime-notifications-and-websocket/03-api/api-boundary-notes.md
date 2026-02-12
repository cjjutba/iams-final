# API Boundary Notes

## Auth Boundary
- WebSocket endpoint (`WS /ws/{user_id}`) requires Supabase JWT — same auth model as protected HTTP routes (MOD-01).
- JWT passed as `token` query parameter (not `Authorization` header, due to WebSocket handshake limitations).
- System-internal publishing functions (FUN-08-02 to FUN-08-04) are backend service calls — no auth boundary.

## System-Internal vs User-Facing
- **User-Facing:** FUN-08-01 (connect), FUN-08-05 (reconnect/cleanup) — exposed via `WS /ws/{user_id}`.
- **System-Internal:** FUN-08-02, FUN-08-03, FUN-08-04 — invoked by upstream modules, no HTTP/WS endpoint.

## Ownership Boundaries
- `MOD-06` owns attendance computation and state transitions → invokes FUN-08-02.
- `MOD-07` owns presence scans and early-leave detection → invokes FUN-08-03.
- `MOD-08` owns realtime transport and event fanout only.

## Input Contracts Into MOD-08
| Source | Function | Payload |
|---|---|---|
| MOD-06 (`attendance_service.py`) | FUN-08-02 | `{ student_id, schedule_id, status, timestamp }` |
| MOD-07 (`presence_service.py`) | FUN-08-03 | `{ student_id, student_name?, schedule_id, detected_at, consecutive_misses? }` |
| Session finalization | FUN-08-04 | `{ schedule_id, date, summary: { present, late, early_leave, absent } }` |

## Output Contracts From MOD-08
- WebSocket event messages to connected mobile clients (envelope: `{ "type": "...", "data": { ... } }`).
- Optional delivery logs for observability (if `WS_ENABLE_DELIVERY_LOGS` is enabled).

## Related Modules
| Module | Integration |
|---|---|
| MOD-01 | JWT verification middleware (`get_current_user`), shared auth dependency |
| MOD-02 | User deletion triggers WebSocket disconnection and map cleanup |
| MOD-06 | Attendance service triggers FUN-08-02 for status change events |
| MOD-07 | Presence service triggers FUN-08-03 for early-leave alert events |
| MOD-09 | Student mobile app receives WebSocket events (SCR-018) |
| MOD-10 | Faculty mobile app receives WebSocket events (SCR-021, SCR-025, SCR-029) |

## Payload Evolution and Versioning
- Event payloads are additive-only for MVP: new optional fields OK, never remove required fields.
- If breaking change needed, create new event type (e.g., `attendance_update_v2`).
- Mobile clients must ignore unknown optional fields gracefully.
- Version field NOT required in MVP events.

## Coordination Rules
- Any upstream payload shape change must update:
  1. `03-api/event-*.md` files
  2. `04-data/event-payload-schema.md`
  3. `05-screens/state-matrix.md` if UI states are impacted
  4. `10-traceability/traceability-matrix.md`
- Event envelope format: `{ "type": "...", "data": { ... } }` (WebSocket messages).
- HTTP error responses (if any added): `{ "success": false, "error": { "code": "", "message": "" } }` — no `details` array.
