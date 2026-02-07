# Profile Screen Flows

## Student Profile View Flow
1. Open `SCR-015` StudentProfileScreen.
2. Call `GET /users/{id}` for current user context.
3. Render safe profile fields.

## Student Profile Edit Flow
1. Open `SCR-016` StudentEditProfileScreen.
2. Edit allowed fields.
3. Submit `PATCH /users/{id}`.
4. On success, refresh profile view.

## Faculty Profile View/Edit Flows
1. Open `SCR-027` or `SCR-028`.
2. Use same get/update endpoint pattern.
3. Enforce field restrictions and role-aware behavior.

## Admin User Flow (API-Level)
1. List users via `GET /users?role=...`.
2. Inspect individual user via `GET /users/{id}`.
3. Apply lifecycle action via `DELETE /users/{id}` when needed.
