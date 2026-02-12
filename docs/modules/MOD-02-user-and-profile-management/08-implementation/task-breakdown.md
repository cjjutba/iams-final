# Task Breakdown

## Task List
| Task ID | Function | Task | Owner/Agent |
|---|---|---|---|
| MOD2-T01 | Setup | Verify Supabase JWT middleware and user repository from MOD-01 | backend-core-specialist |
| MOD2-T02 | FUN-02-02 | Build get-user endpoint with scope checks, full response fields (phone, email_confirmed, created_at) | backend-core-specialist |
| MOD2-T03 | FUN-02-03 | Implement update-user endpoint + field rules (editable: name, phone; immutable: email; admin-only: role, student_id, is_active) | business-logic-specialist |
| MOD2-T04 | FUN-02-01 | Implement list-users endpoint with pagination/filter (admin-only) | backend-core-specialist |
| MOD2-T05 | FUN-02-04 | Implement permanent delete with Supabase Auth Admin API cleanup + face_registrations + FAISS coordination | database-specialist |
| MOD2-T06 | FUN-02-04 | Implement rollback logic for Supabase Auth deletion failure | auth-security-specialist |
| MOD2-T07 | SCR set | Integrate student/faculty profile screens with phone field and email as read-only | mobile-frontend-specialist |
| MOD2-T08 | QA | Add user/profile unit, integration, and E2E tests (including phone, email immutability, Supabase Auth delete) | test-automation-specialist |
| MOD2-T09 | Docs | Update traceability and changelog | docs-writer |

## Done Definition per Task
- Code merged
- Tests pass
- Traceability row updated
- Related docs updated when behavior changes
