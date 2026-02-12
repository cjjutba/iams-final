# Task Breakdown

## Task List
| Task ID | Function | Task | Owner/Agent |
|---|---|---|---|
| MOD7-T00 | Setup | Verify auth middleware, models, timezone config, and MOD-05/06 dependencies | backend-core-specialist |
| MOD7-T01 | FUN-07-01 | Implement session lifecycle state manager | tracking-presence-specialist |
| MOD7-T02 | FUN-07-02 | Implement periodic scan evaluator at SCAN_INTERVAL | tracking-presence-specialist |
| MOD7-T03 | FUN-07-03 | Implement miss counter transitions (deterministic reset/increment) | business-logic-specialist |
| MOD7-T04 | FUN-07-04 | Implement early-leave flag logic with dedup and attendance status update | tracking-presence-specialist |
| MOD7-T05 | FUN-07-05 | Implement presence score computation with zero-scan handling | business-logic-specialist |
| MOD7-T06 | FUN-07-06 | Implement presence logs and early-leave endpoints with Supabase JWT auth | backend-core-specialist |
| MOD7-T07 | SCR set | Integrate faculty detail/alerts screens with presence API and auth handling | mobile-api-integration |
| MOD7-T08 | QA | Add presence scenario tests (unit + integration + scenario, including auth) | test-automation-specialist |
| MOD7-T09 | QA | Verify auth enforcement for all role combinations (401/403) | test-automation-specialist |
| MOD7-T10 | Docs | Update traceability and changelog | docs-writer |

## Done Definition per Task
- Code merged.
- Tests pass.
- Traceability row updated.
- Auth enforcement verified (401/403 for appropriate scenarios).
- Related docs updated when behavior changes.
