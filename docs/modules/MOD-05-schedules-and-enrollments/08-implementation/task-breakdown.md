# Task Breakdown

## Task List
| Task ID | Function | Task | Owner/Agent |
|---|---|---|---|
| MOD5-T01 | Setup | Verify auth middleware, models, and timezone config | backend-core-specialist |
| MOD5-T02 | FUN-05-01 | Implement schedule list endpoint with day/filter params and Supabase JWT | backend-core-specialist |
| MOD5-T03 | FUN-05-02 | Implement schedule detail endpoint with joins (faculty name, room name) | backend-core-specialist |
| MOD5-T04 | FUN-05-03 | Implement admin schedule creation with validation and role check | business-logic-specialist |
| MOD5-T05 | FUN-05-04 | Implement role-aware `schedules/me` query (faculty by faculty_id, student by enrollments) | business-logic-specialist |
| MOD5-T06 | FUN-05-05 | Implement schedule roster endpoint with access control (admin/faculty/enrolled student) | database-specialist |
| MOD5-T07 | SCR set | Integrate student/faculty schedule screens with API and auth handling | mobile-api-integration |
| MOD5-T08 | QA | Add schedule/enrollment/auth tests (unit + integration + E2E) | test-automation-specialist |
| MOD5-T09 | QA | Verify roster access control for all role combinations | test-automation-specialist |
| MOD5-T10 | Docs | Update traceability and changelog | docs-writer |

## Done Definition per Task
- Code merged
- Tests pass
- Traceability row updated
- Auth enforcement verified (401/403 for appropriate scenarios)
- Related docs updated when behavior changes
