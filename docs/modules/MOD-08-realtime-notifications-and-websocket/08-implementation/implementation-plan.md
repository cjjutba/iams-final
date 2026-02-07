# Implementation Plan

## Phase 1: Connection Foundation
- Implement authenticated `WS /ws/{user_id}` endpoint.
- Add connection manager and map registration/removal.

## Phase 2: Event Publishing Pipeline
- Implement event envelope builders for:
  - `attendance_update`
  - `early_leave`
  - `session_end`
- Wire publisher calls from attendance/presence/session flows.

## Phase 3: Reliability Controls
- Add heartbeat and stale connection cleanup.
- Add reconnect-safe handling to avoid duplicate stale entries.

## Phase 4: Mobile Integration
- Integrate websocket service with target screens.
- Map event types to UI actions/state updates.

## Phase 5: Validation and Hardening
- Run T08 unit/integration/scenario tests.
- Validate latency and reconnect stability for MVP demo.
