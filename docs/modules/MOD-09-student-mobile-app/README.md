# MOD-09 Student Mobile App Documentation Pack

## Purpose
This folder is the full implementation reference for Module 9.
When implementing student mobile features, use this folder as the primary source of truth.

## Auth Context
MOD-09 spans both **pre-auth** and **post-auth** flows:
- **Pre-auth screens** (no JWT required): SCR-001, SCR-002, SCR-003, SCR-004, SCR-006, SCR-007, SCR-008, SCR-009, SCR-010
- **Post-auth screens** (JWT required): SCR-011, SCR-012, SCR-013, SCR-014, SCR-015, SCR-016, SCR-017, SCR-018

Registration (FUN-09-03) is a special case: Steps 1-2 are pre-auth, Step 3 (face registration) and Step 4 (review/submit) complete the account creation. After registration completes, the user receives tokens and transitions to post-auth.

## Coverage
This pack documents:
- Goal and governance rules
- MVP scope boundaries
- Module catalog and capability matrix
- Detailed function specifications (`FUN-09-01` to `FUN-09-06`)
- Consumed API inventory and endpoint-level contracts
- Mobile state/data model inventory
- Screen inventory and student-flow behavior
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
- `04-data/`: mobile local state and storage inventory
- `05-screens/`: student screen inventory, flows, UI states
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
- Module: `MOD-09`
- Functions: `FUN-09-01` to `FUN-09-06`
- Screens: `SCR-001` to `SCR-018` (student path scope)

## Definition of Documentation Completion
Module 9 documentation is considered complete when:
- All files in this folder are populated and internally consistent.
- All six functions have acceptance criteria and test cases.
- Screen flows, consumed API docs, and state docs are aligned.
- Auth context (pre-auth vs post-auth) is documented per screen and endpoint.
- Timezone display rules are documented.
- Traceability matrix has no missing mappings.
