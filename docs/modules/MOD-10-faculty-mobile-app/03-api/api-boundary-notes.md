# API Boundary Notes

## Ownership Boundaries
- `MOD-10` owns faculty mobile UX and local state behavior.
- Backend modules own endpoint contracts and business rules.

## Upstream Module Contracts Used
- `MOD-01`: faculty authentication/session endpoints
- `MOD-02`: profile endpoint operations
- `MOD-05`: schedule and class roster data
- `MOD-06`: live/today/manual attendance endpoints
- `MOD-07`: early-leave and presence log endpoints
- `MOD-08`: websocket realtime transport

## Contract Drift Policy
If any upstream contract changes:
1. Update `03-api/` docs in this module pack.
2. Update impacted screen-state docs in `05-screens/`.
3. Update `10-traceability/traceability-matrix.md` before merge.
