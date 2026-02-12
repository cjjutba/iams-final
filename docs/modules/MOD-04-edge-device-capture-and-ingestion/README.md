# MOD-04 Edge Device Capture and Ingestion Documentation Pack

## Purpose
This folder is the full implementation reference for Module 4.
When implementing edge capture and ingestion features, use this folder as the primary source of truth.

## Auth Context
MOD-04 is an **edge-device module** — it runs on the Raspberry Pi, not in a browser or mobile app. Edge devices do **not** hold Supabase JWTs. Instead, the edge→backend connection is authenticated via a **shared API key** sent in the `X-API-Key` header, validated against the `EDGE_API_KEY` environment variable on the backend. This pattern was established in MOD-03 for the recognition endpoint and applies equally to `POST /face/process`.

## Coverage
This pack documents:
- Goal and governance rules
- MVP scope boundaries
- Module catalog and capability matrix
- Detailed function specifications (`FUN-04-01` to `FUN-04-05`)
- API inventory and endpoint-level contracts
- Data model and queue lifecycle documentation
- Screen inventory (none for edge runtime) and operation flow notes
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
- `04-data/`: queue model, payload model, operational logs
- `05-screens/`: no UI ownership, runtime flow notes, operational state matrix
- `06-dependencies/`: dependency order, integration points, env config
- `07-testing/`: test strategy, test cases, demo checklist
- `08-implementation/`: implementation plan and task breakdown
- `09-ai-execution/`: AI prompt template, agent routing, output contract, runbook
- `10-traceability/`: mapping from functions to API/data/tests

## Canonical Sources
- `docs/main/architecture.md`
- `docs/main/implementation.md`
- `docs/main/database-schema.md`
- `docs/main/api-reference.md`
- `docs/main/deployment.md`

## Module IDs
- Module: `MOD-04`
- Functions: `FUN-04-01` to `FUN-04-05`
- Screens: none (edge runtime module)

## Definition of Documentation Completion
Module 4 documentation is considered complete when:
- All files in this folder are populated and internally consistent.
- Every function has test cases and acceptance criteria.
- API docs and queue/retry docs reference the same behavior.
- Edge→backend authentication uses shared API key (`X-API-Key` header).
- Crop size boundary is documented (edge crops ~112x112, backend resizes to 160x160 for FaceNet).
- Traceability matrix has no missing mappings.
