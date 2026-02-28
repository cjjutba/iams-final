# Agent Routing

## Recommended Agent Roles
- `mobile-frontend-specialist.md`: faculty screen implementation and navigation flows
- `mobile-state-manager.md`: session/store/realtime state behavior
- `mobile-api-integration.md`: API and websocket integration for faculty workflows

## Routing Rules
1. Use frontend specialist for screen and route implementation.
2. Use state manager for auth restore, live roster state, and alert/feed state.
3. Use API integration specialist for endpoint contracts and manual entry behaviors.
4. Coordinate backend specialists only when contract mismatch is discovered.

## Handoff Contract
Every handoff should include:
- Target `FUN-10-*` IDs
- Files touched
- Tests run and outcomes
- Documentation updates applied
