# Implementation Plan

## Phase 1: Faculty Auth Foundation
- Implement faculty login and secure session restore.
- Guard faculty-only route stack by role/session state.

## Phase 2: Schedule and Live Monitoring
- Implement faculty schedule screens and active class resolution.
- Implement live attendance screen baseline data load.

## Phase 3: Manual Attendance and Alert Features
- Implement manual attendance form and submission flow.
- Implement early-leave alert screens and summary cards.

## Phase 4: Profile and Notification Experience
- Implement profile view/edit flows.
- Integrate notification feed and websocket updates.

## Phase 5: Validation and Hardening
- Execute `T10-*` tests.
- Verify reconnect behavior and UI state coverage for MVP readiness.
