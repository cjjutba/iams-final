# Agent Routing

## Recommended Agent Assignment
| Work Type | Primary Agent | Secondary Agent |
|---|---|---|
| attendance endpoint scaffolding | `backend-core-specialist.md` | `business-logic-specialist.md` |
| status/dedup/manual rules | `business-logic-specialist.md` | `database-specialist.md` |
| live attendance and event alignment | `websocket-specialist.md` | `tracking-presence-specialist.md` |
| mobile attendance integration | `mobile-api-integration.md` | `mobile-state-manager.md` |
| testing automation | `test-automation-specialist.md` | `backend-core-specialist.md` |
| documentation sync | `docs-writer.md` | `backend-core-specialist.md` |

## Routing Rules
- Manual override behavior changes require test updates.
- Status model changes require cross-module review (`MOD-07`, `MOD-08`).
- API contract changes require docs update before implementation.
