# Task Breakdown

## Task List
| Task ID | Function | Task | Owner/Agent |
|---|---|---|---|
| MOD9-T00 | Setup | Verify backend endpoints, env vars, Axios interceptors, SecureStore | mobile-frontend-specialist |
| MOD9-T01 | FUN-09-01 | Implement splash/onboarding/welcome routing (pre-auth) | mobile-frontend-specialist |
| MOD9-T02 | FUN-09-02 | Implement student login, token persistence, session restore | mobile-frontend-specialist |
| MOD9-T03 | FUN-09-03 | Implement registration Step 1 (verify student ID, pre-auth) | mobile-forms-validator |
| MOD9-T04 | FUN-09-03 | Implement registration Step 2 (account setup, pre-auth → tokens) | mobile-forms-validator |
| MOD9-T05 | FUN-09-03 | Implement registration Step 3 (face capture, post-auth) | mobile-camera-face-capture |
| MOD9-T06 | FUN-09-03 | Implement registration Step 4 (review, step gating) | mobile-frontend-specialist |
| MOD9-T07 | FUN-09-04 | Implement home/schedule/history/detail views (post-auth) | mobile-frontend-specialist |
| MOD9-T08 | FUN-09-05 | Implement profile view/edit and face re-registration (post-auth) | mobile-frontend-specialist |
| MOD9-T09 | FUN-09-06 | Implement notifications WebSocket flow (JWT via query param) | websocket-mobile-specialist |
| MOD9-T10 | QA | Run T09 tests (unit + integration + scenario) | test-automation-specialist |
| MOD9-T11 | QA | Verify auth enforcement (pre-auth vs post-auth, close codes) | test-automation-specialist |
| MOD9-T12 | Docs | Update traceability and changelog | docs-writer |

## Done Definition per Task
- Code merged.
- Tests pass.
- Traceability row updated.
- Pre-auth vs post-auth behavior verified for relevant endpoints.
- Timestamps display in Asia/Manila timezone (+08:00).
- Error envelope handled without assuming `details` array.
- Design system constraints followed (see `mvp-scope.md`).
- Related docs updated when behavior changes.
