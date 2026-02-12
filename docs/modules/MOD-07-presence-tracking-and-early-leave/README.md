# MOD-07 Presence Tracking and Early Leave Documentation Pack

## Purpose
This folder is the full implementation reference for Module 7.
When implementing continuous presence and early-leave logic, use this folder as the primary source of truth.

## Auth Context
MOD-07 has two categories of functions:
- **System-Internal (FUN-07-01 to FUN-07-05):** Invoked by the presence service scan loop — no HTTP endpoints, no JWT required.
- **User-Facing API (FUN-07-06):** Requires **Supabase JWT** (`Authorization: Bearer <token>`).

Role-based access for FUN-07-06 endpoints:
- **GET /api/v1/presence/{attendance_id}/logs** — faculty or admin (view presence detail for an attendance record).
- **GET /api/v1/presence/early-leaves** — faculty or admin (view early-leave events for a schedule/date).
- 401 for missing/invalid JWT.
- 403 for insufficient role (students cannot access presence endpoints directly).
- No API key auth (that pattern is for MOD-03/MOD-04 edge devices only).

## Coverage
This pack documents:
- Goal and governance rules
- MVP scope boundaries
- Module catalog and capability matrix
- Detailed function specifications (`FUN-07-01` to `FUN-07-06`)
- API inventory and endpoint-level contracts
- Data model, thresholds, and session-state documentation
- Screen inventory and presence-monitoring flow behavior
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
- `04-data/`: presence logs, early leave events, threshold/state models
- `05-screens/`: screen inventory, presence-monitoring flows, UI states
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
- Module: `MOD-07`
- Functions: `FUN-07-01` to `FUN-07-06`
- Screens: `SCR-022`, `SCR-023`, `SCR-025`

## Definition of Documentation Completion
Module 7 documentation is considered complete when:
- All files in this folder are populated and internally consistent.
- Every function has test cases and acceptance criteria.
- API docs and screen docs reference the same behavior.
- Traceability matrix has no missing mappings.
- Auth rules (Supabase JWT, role requirements, 401/403 responses) are documented per endpoint.
- Timezone handling (`TIMEZONE` env var, Asia/Manila default) is documented for session boundaries and date queries.
- Response envelope format (`success`, `data`, `message` for success; `success`, `error` for failure) is consistent across all endpoint contracts.
- System-internal functions (FUN-07-01 to FUN-07-05) are clearly distinguished from user-facing API functions (FUN-07-06).
