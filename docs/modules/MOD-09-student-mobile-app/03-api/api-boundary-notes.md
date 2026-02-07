# API Boundary Notes

## Ownership Boundaries
- `MOD-09` owns student mobile UX and local state behavior.
- Backend modules own endpoint contracts and business logic.

## Upstream Module Contracts Used
- `MOD-01`: auth and identity endpoints.
- `MOD-02`: profile endpoint updates.
- `MOD-03`: face registration/status endpoints.
- `MOD-05`: student schedule endpoint.
- `MOD-06`: student attendance endpoints.
- `MOD-08`: websocket event transport.

## Contract Drift Policy
If any upstream payload or auth requirement changes:
1. Update `03-api/` docs in this module.
2. Update impacted screen-state docs in `05-screens/`.
3. Update traceability matrix before implementation merge.
