# Working Rules

## Source-of-Truth Rules
1. This folder is the implementation reference for `MOD-07`.
2. If implementation needs behavior not documented here, update docs first.
3. If docs conflict, create an ADR and resolve before coding.
4. Every implementation task must reference `MOD-07` and at least one `FUN-07-*` ID.

## Scope Control
- Implement only `FUN-07-01` to `FUN-07-06` under this module.
- Do not implement websocket transport details (owned by `MOD-08`).
- FUN-07-01 to FUN-07-05 are system-internal service functions (no HTTP endpoints).
- FUN-07-06 is the only user-facing API function.

## Auth Rules
1. All user-facing endpoints (FUN-07-06) require Supabase JWT (`Authorization: Bearer <token>`).
2. GET /presence/{attendance_id}/logs requires faculty or admin role.
3. GET /presence/early-leaves requires faculty or admin role.
4. Return 401 for missing or invalid JWT.
5. Return 403 for insufficient role (e.g., student accessing faculty-only endpoints).
6. No API key auth — that pattern is for MOD-03/MOD-04 edge devices only.
7. System-internal functions (FUN-07-01 to FUN-07-05) do not require JWT (invoked by backend service loop).

## Timezone Rules
1. `TIMEZONE` env var configures the system timezone (default: Asia/Manila, +08:00).
2. Session date/time boundaries use the configured timezone, not UTC.
3. "Today" queries for session context use configured timezone.

## Quality Rules
- Scan interval and threshold values must be configurable via env vars.
- Miss-counter resets and increments must be deterministic.
- Early-leave flags require threshold condition fulfillment.
- Presence logs should support accurate audit/replay.
- Response envelope: `{ "success": true, "data": {}, "message": "" }` for success; `{ "success": false, "error": { "code": "", "message": "" } }` for errors (no `details` array).

## Delivery Rules
- Each commit/PR should include traceability, for example:
  - `Implements MOD-07 FUN-07-04`
- Any API contract change must update:
  - `03-api/api-inventory.md`
  - relevant endpoint file(s)
  - `10-traceability/traceability-matrix.md`

## Change Process
1. Propose doc updates.
2. Review consistency across API/data/screens/testing docs.
3. Implement code.
4. Run tests.
5. Update traceability and changelog.
