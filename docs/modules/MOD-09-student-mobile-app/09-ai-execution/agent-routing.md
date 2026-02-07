# Agent Routing

## Recommended Agent Roles
- `mobile-frontend-specialist.md`: screen implementation and navigation behavior
- `mobile-state-manager.md`: app/store state modeling and hydration
- `mobile-api-integration.md`: endpoint integration, error handling, token flow

## Routing Rules
1. Use mobile frontend specialist for screen and navigation-heavy work.
2. Use state manager for session/cache/store logic.
3. Use API integration specialist for consumed endpoints and websocket behavior.
4. Use backend specialist only if contract mismatch requires backend coordination.

## Handoff Contract
Every handoff should include:
- Target `FUN-09-*` IDs
- Files touched
- Tests run
- Documentation updates made
