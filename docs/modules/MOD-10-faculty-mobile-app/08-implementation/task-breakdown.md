# Task Breakdown

## Task List
| Task ID | Function | Task | Owner/Agent |
|---|---|---|---|
| MOD10-T00 | Setup | Verify backend endpoints, env vars, Axios interceptors, SecureStore | mobile-frontend-specialist |
| MOD10-T01 | FUN-10-01 | Implement faculty login, token persistence, session restore | mobile-frontend-specialist |
| MOD10-T02 | FUN-10-01 | Implement forgot password screen (pre-auth) | mobile-frontend-specialist |
| MOD10-T03 | FUN-10-02 | Implement faculty home and schedule screens | mobile-frontend-specialist |
| MOD10-T04 | FUN-10-02 | Implement active class resolution (timezone-aware) | mobile-frontend-specialist |
| MOD10-T05 | FUN-10-03 | Implement live attendance screen with WebSocket | websocket-mobile-specialist |
| MOD10-T06 | FUN-10-04 | Implement manual attendance form and submission | mobile-forms-validator |
| MOD10-T07 | FUN-10-05 | Implement early-leave alerts and class detail views | mobile-frontend-specialist |
| MOD10-T08 | FUN-10-05 | Implement reports and class summary views | mobile-frontend-specialist |
| MOD10-T09 | FUN-10-06 | Implement faculty profile view/edit | mobile-frontend-specialist |
| MOD10-T10 | FUN-10-06 | Implement notification feed with WebSocket | websocket-mobile-specialist |
| MOD10-T11 | QA | Run T10 tests (unit + integration + scenario) | test-automation-specialist |
| MOD10-T12 | QA | Verify auth enforcement (pre-auth vs post-auth, close codes) | test-automation-specialist |
| MOD10-T13 | Docs | Update traceability and changelog | docs-writer |

## Done Definition per Task
- Code merged.
- Tests pass.
- Traceability row updated.
- Pre-auth vs post-auth behavior verified for relevant endpoints.
- Timestamps display in Asia/Manila timezone (+08:00).
- Error envelope handled without assuming `details` array.
- Design system constraints followed (see `mvp-scope.md`).
- Related docs updated when behavior changes.
