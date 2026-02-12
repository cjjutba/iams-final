# MOD-06 Attendance Records Documentation Pack

## Purpose
This folder is the full implementation reference for Module 6.
When implementing attendance record features, use this folder as the primary source of truth.

## Auth Context
All MOD-06 endpoints require **Supabase JWT** (`Authorization: Bearer <token>`). Role-based access:
- **GET /attendance/today** — faculty or admin (view class attendance for a schedule).
- **GET /attendance/me** — any authenticated user (students see own, faculty see own classes).
- **POST /attendance/mark** — internal/system only (triggered by recognition pipeline, not user-facing).
- **POST /attendance/manual** — faculty or admin only (manual override with audit trail).
- **GET /attendance/history** — faculty or admin (filtered attendance history by schedule/date range).
- **GET /attendance/live** — faculty or admin (real-time roster for active class).
- No API key auth (that pattern is for MOD-03/MOD-04 edge devices).

## Coverage
This pack documents:
- Goal and governance rules
- MVP scope boundaries
- Module catalog and capability matrix
- Detailed function specifications (`FUN-06-01` to `FUN-06-06`)
- API inventory and endpoint-level contracts
- Data model and attendance status documentation
- Screen inventory and attendance flow behavior
- Module dependency order and integration points
- Testing strategy and acceptance criteria
- AI execution templates and output contract
- Traceability matrix

## Quick Start
1. Read `00-governance/goal-and-objectives.md`.
2. Read `00-governance/working-rules.md`.
3. Read `02-specification/function-specifications.md`.
4. Read `03-api/api-inventory.md` and endpoint docs.
5. Read `10-traceability/traceability-matrix.md` before implementation.

## Folder Map
- `00-governance/`: goal, rules, scope, change control
- `01-catalog/`: module catalog, capabilities, glossary
- `02-specification/`: module specs, function specs, business rules, acceptance criteria
- `03-api/`: API inventory and endpoint contracts
- `04-data/`: data model, attendance fields, status and dedup/override policy
- `05-screens/`: screen inventory, attendance flows, UI states
- `06-dependencies/`: dependency order, integration points, env config
- `07-testing/`: test strategy, test cases, demo checklist
- `08-implementation/`: implementation plan and task breakdown
- `09-ai-execution/`: AI prompt template, agent routing, output contract, runbook
- `10-traceability/`: mapping from functions to API/data/screens/tests

## Canonical Sources
- `docs/main/architecture.md`
- `docs/main/api-reference.md`
- `docs/main/database-schema.md`
- `docs/main/implementation.md`
- `docs/main/prd.md`

## Module IDs
- Module: `MOD-06`
- Functions: `FUN-06-01` to `FUN-06-06`
- Screens: `SCR-011`, `SCR-013`, `SCR-014`, `SCR-019`, `SCR-021`, `SCR-024`

## Definition of Documentation Completion
Module 6 documentation is considered complete when:
- All files in this folder are populated and internally consistent.
- Every function has test cases and acceptance criteria.
- API docs and screen docs reference the same behavior.
- Traceability matrix has no missing mappings.
- Auth rules (Supabase JWT, role requirements, 401/403 responses) are documented per endpoint.
- Timezone handling (TIMEZONE env var, Asia/Manila default) is documented for all date/time fields.
- Response envelope format (`success`, `data`, `message` for success; `success`, `error` for failure) is consistent across all endpoint contracts.
