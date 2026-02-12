# Task Breakdown

## Task List
| Task ID | Function | Task | Owner/Agent |
|---|---|---|---|
| MOD6-T01 | Setup | Verify auth middleware, models, and timezone config | backend-core-specialist |
| MOD6-T02 | FUN-06-01 | Implement attendance mark/upsert logic with dedup | backend-core-specialist |
| MOD6-T03 | FUN-06-02 | Implement today's attendance endpoint, summary, and role check | backend-core-specialist |
| MOD6-T04 | FUN-06-03 | Implement role-scoped student/faculty attendance history | business-logic-specialist |
| MOD6-T05 | FUN-06-04 | Implement filtered attendance history with schedule ownership check | business-logic-specialist |
| MOD6-T06 | FUN-06-05 | Implement faculty manual attendance entry with audit trail | business-logic-specialist |
| MOD6-T07 | FUN-06-06 | Implement live attendance endpoint with session detection | websocket-specialist |
| MOD6-T08 | SCR set | Integrate student/faculty attendance screens with API and auth handling | mobile-api-integration |
| MOD6-T09 | QA | Add attendance tests (unit + integration + E2E, including auth scenarios) | test-automation-specialist |
| MOD6-T10 | QA | Verify auth enforcement for all role combinations (401/403) | test-automation-specialist |
| MOD6-T11 | Docs | Update traceability and changelog | docs-writer |

## Done Definition per Task
- Code merged
- Tests pass
- Traceability row updated
- Auth enforcement verified (401/403 for appropriate scenarios)
- Related docs updated when behavior changes
