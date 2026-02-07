# Student App Screen Flows

## Entry and Auth Flow
1. `SCR-001` Splash evaluates first launch and session state.
2. New users go to `SCR-002` Onboarding, then `SCR-003` Welcome.
3. Student route goes to `SCR-004` StudentLogin or registration flow.
4. Forgot password path uses `SCR-006`.

## Registration Flow (4 Steps)
1. `SCR-007`: Verify student ID.
2. `SCR-008`: Collect account details.
3. `SCR-009`: Capture/upload 3-5 face images.
4. `SCR-010`: Review and submit.

## Student Portal Flow
1. After auth, land on `SCR-011` StudentHome.
2. Navigate to `SCR-012` schedule and `SCR-013` history.
3. Open detailed record in `SCR-014`.
4. Manage profile via `SCR-015` and `SCR-016`.
5. Re-register face via `SCR-017`.
6. View notifications in `SCR-018`.

## Realtime Notification Flow
1. On `SCR-018`, open websocket for current user.
2. Render incoming event cards by type.
3. On disconnect, show reconnecting state and retry.
4. Resume updates after reconnect without app restart.
