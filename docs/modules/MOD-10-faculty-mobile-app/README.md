# MOD-10 Faculty Mobile App Documentation Pack

## Purpose
This folder is the full implementation reference for Module 10.
When implementing faculty mobile features, use this folder as the primary source of truth.

## Auth Context
MOD-10 spans pre-auth and post-auth screens within one mobile application:
- **Pre-auth screens** (SCR-005, SCR-006): Faculty login and forgot password — no JWT required.
- **Post-auth screens** (SCR-019 to SCR-029): All faculty portal screens — require backend-issued JWT via `Authorization: Bearer <token>` header.
- **WebSocket**: JWT passed via `token` query parameter (not header). Close codes 4001 (unauthorized → login redirect) and 4003 (forbidden → error message).
- Faculty accounts are **pre-seeded only** — no self-registration in MVP.

## Coverage
This pack documents:
- Goal and governance rules
- MVP scope boundaries
- Module catalog and capability matrix
- Detailed function specifications (`FUN-10-01` to `FUN-10-06`)
- Consumed API inventory and endpoint-level contracts
- Mobile state/data model inventory
- Faculty screen inventory and flow behavior
- Module dependency order and integration points
- Testing strategy and acceptance criteria
- AI execution templates and output contract
- Traceability matrix

## Quick Start
1. Read `00-governance/goal-and-objectives.md`.
2. Read `00-governance/working-rules.md`.
3. Read `02-specification/function-specifications.md`.
4. Read `03-api/api-inventory.md`.
5. Read `10-traceability/traceability-matrix.md` before implementation.

## Folder Map
- `00-governance/`: goal, rules, scope, change control
- `01-catalog/`: module catalog, capabilities, glossary
- `02-specification/`: module specs, function specs, business rules, acceptance criteria
- `03-api/`: consumed API contracts and boundary notes
- `04-data/`: faculty mobile local state and storage inventory
- `05-screens/`: faculty screen inventory, flows, UI states
- `06-dependencies/`: dependency order, integration points, env config
- `07-testing/`: test strategy, test cases, demo checklist
- `08-implementation/`: implementation plan and task breakdown
- `09-ai-execution/`: AI prompt template, agent routing, output contract, runbook
- `10-traceability/`: mapping from functions to APIs/data/screens/tests

## Canonical Sources
- `docs/main/architecture.md`
- `docs/main/api-reference.md`
- `docs/main/implementation.md`
- `docs/main/database-schema.md`
- `docs/main/prd.md`

## Module IDs
- Module: `MOD-10`
- Functions: `FUN-10-01` to `FUN-10-06`
- Screens: `SCR-005`, `SCR-006`, `SCR-019` to `SCR-029`

## Definition of Documentation Completion
Module 10 documentation is considered complete when:
- All files in this folder are populated and internally consistent.
- All six functions have acceptance criteria and test cases.
- Screen flows, consumed API docs, and state docs are aligned.
- Pre-auth vs post-auth behavior is documented for every screen and endpoint.
- Timestamps display in Asia/Manila timezone (+08:00).
- Error envelope format documented (no `details` array).
- Design system constraints followed.
- Traceability matrix has no missing mappings.
