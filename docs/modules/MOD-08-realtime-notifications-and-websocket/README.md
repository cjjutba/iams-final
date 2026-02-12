# MOD-08 Realtime Notifications and WebSocket Documentation Pack

## Purpose
This folder is the full implementation reference for Module 8.
When implementing realtime notification delivery and WebSocket behavior, use this folder as the primary source of truth.

## Auth Context
MOD-08 has two categories of functions:
- **User-Facing (FUN-08-01, FUN-08-05):** WebSocket endpoint at `WS /ws/{user_id}` — requires **Supabase JWT** (passed as query parameter `token` during handshake).
- **System-Internal (FUN-08-02 to FUN-08-04):** Backend service functions that publish events to connected sockets — no JWT required (invoked by MOD-06/MOD-07 service layer).

WebSocket auth rules:
- JWT `sub` claim must match path `user_id` — reject with close code 4003 if mismatch.
- Invalid/missing/expired JWT — reject with close code 4001.
- All authenticated roles (student, faculty, admin) can connect to their own WebSocket.
- No API key auth (that pattern is for MOD-03/MOD-04 edge devices only).

## Coverage
This pack documents:
- Goal and governance rules
- MVP scope boundaries
- Module catalog and capability matrix
- Detailed function specifications (`FUN-08-01` to `FUN-08-05`)
- WebSocket API inventory and event-level contracts
- Connection-state and payload model documentation
- Screen inventory and notification UI flow behavior
- Module dependency order and integration points
- Testing strategy and acceptance criteria
- AI execution templates and output contract
- Traceability matrix

## Quick Start
1. Read `00-governance/goal-and-objectives.md`.
2. Read `00-governance/working-rules.md`.
3. Read `02-specification/function-specifications.md`.
4. Read `03-api/api-inventory.md` and event docs.
5. Read `10-traceability/traceability-matrix.md` before implementation.

## Folder Map
- `00-governance/`: goal, rules, scope, change control
- `01-catalog/`: module catalog, capabilities, glossary
- `02-specification/`: module specs, function specs, business rules, acceptance criteria
- `03-api/`: WebSocket endpoint and event contracts
- `04-data/`: connection map, payload schema, delivery log model
- `05-screens/`: screen inventory, notification flows, UI states
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
- Module: `MOD-08`
- Functions: `FUN-08-01` to `FUN-08-05`
- Screens: `SCR-018`, `SCR-021`, `SCR-025`, `SCR-029`

## Definition of Documentation Completion
Module 8 documentation is considered complete when:
- All files in this folder are populated and internally consistent.
- Every function has acceptance criteria and test cases.
- Event payload docs, mobile state docs, and API docs match.
- Traceability matrix has no missing mappings.
- Auth rules (Supabase JWT, user identity matching, close codes 4001/4003) are documented for WebSocket endpoint.
- System-internal functions (FUN-08-02 to FUN-08-04) are clearly distinguished from user-facing functions (FUN-08-01, FUN-08-05).
- Timezone handling (`TIMEZONE` env var, Asia/Manila default) is documented for event timestamps.
- Event envelope format (`{ "type": "...", "data": { ... } }`) is consistent across all event contracts.
