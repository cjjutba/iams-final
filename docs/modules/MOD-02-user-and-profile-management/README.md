# MOD-02 User and Profile Management Documentation Pack

## Purpose
This folder is the full implementation reference for Module 2.
When implementing user/profile features, use this folder as the primary source of truth.

## Coverage
This pack documents:
- Goal and governance rules
- MVP scope boundaries
- Module catalog and capability matrix
- Detailed function specifications (`FUN-02-01` to `FUN-02-04`)
- API inventory and endpoint-level contracts
- Data model and lifecycle documentation
- Screen inventory and profile flow behavior
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
- `04-data/`: data model, users fields, lifecycle and soft-delete policy
- `05-screens/`: screen inventory, profile flows, UI states
- `06-dependencies/`: dependency order, integration points, env config
- `07-testing/`: test strategy, test cases, demo checklist
- `08-implementation/`: implementation plan and task breakdown
- `09-ai-execution/`: AI prompt template, agent routing, output contract, runbook
- `10-traceability/`: mapping from functions to API/data/screens/tests

## Canonical Sources
- `docs/main/master-blueprint.md`
- `docs/main/api-reference.md`
- `docs/main/database-schema.md`
- `docs/main/technical-specification.md`
- `docs/main/prd.md`
- `docs/main/testing.md`
- `docs/screens/screen-list.md`

## Module IDs
- Module: `MOD-02`
- Functions: `FUN-02-01` to `FUN-02-04`
- Screens: `SCR-015`, `SCR-016`, `SCR-027`, `SCR-028`

## Definition of Documentation Completion
Module 2 documentation is considered complete when:
- All files in this folder are populated and internally consistent.
- Every function has test cases and acceptance criteria.
- API docs and screen docs reference the same behavior.
- Traceability matrix has no missing mappings.
