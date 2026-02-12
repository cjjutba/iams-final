# Changelog (MOD-09)

## 2026-02-12
- **Canonical sources fixed:** Removed `master-blueprint.md`, `technical-specification.md`, `testing.md`, `screen-list.md`. Added `architecture.md`, `implementation.md`, `database-schema.md`, `prd.md` in README.md and folder-file-mapping.md.
- **Auth context added:** New Auth Context sections in README.md, goal-and-objectives.md, module-specification.md, student-mobile-catalog.md, capabilities-matrix.md. Explicit pre-auth (SCR-001 to SCR-008) vs post-auth (SCR-009 to SCR-018) distinction throughout.
- **Auth rules added:** New Auth Rules section in working-rules.md and business-rules.md. Pre-auth endpoints (login, register, verify-student-id) require no JWT. Post-auth endpoints require `Authorization: Bearer <token>`. WebSocket uses JWT via `token` query param. Registration Steps 1-2 pre-auth, Steps 3-4 post-auth.
- **Token architecture documented:** New Token Architecture section in mvp-scope.md. Backend-issued JWT (not Supabase client SDK). Stored in Expo SecureStore. Axios interceptors for auto-attach and 401 refresh. WebSocket uses query param for JWT.
- **Timezone rules documented:** Added Timezone Rules in working-rules.md, mvp-scope.md, environment-config.md. ISO-8601 with +08:00 offset (Asia/Manila). YYYY-MM-DD date filters. `TIMEZONE` env var added.
- **Design system constraints documented:** New Design System Constraints section in mvp-scope.md. Text weight types, Avatar styling, Divider spacing, colors.status limits, snake_case API fields.
- **Error envelope shape documented:** Added HTTP Response Envelope and explicit "no `details` array" note in error-models.md, api-inventory.md, api-boundary-notes.md, glossary.md, business-rules.md, acceptance-criteria.md.
- **WebSocket close codes documented:** Added close codes table (4001/4003/1000/1011) in endpoint-student-notifications.md, error-models.md. Client handling: 4001 → login redirect, 4003 → error message.
- **Pre-auth vs post-auth API table added:** New consolidated table in api-boundary-notes.md listing all 13 endpoints with auth status.
- **Endpoint contracts enhanced:** Added Auth column, request/response examples, and auth context per endpoint in all endpoint-*.md files. Added realistic JSON with 2026 dates and +08:00 offsets.
- **Registration flow enhanced:** Added Caller Context (pre-auth vs post-auth per step), `student_records` table validation, duplicate ID rejection, profile snapshot pre-fill, token return from registration in endpoint-registration-flow.md and function-specifications.md.
- **Service method notes added:** `authService.updateProfile(userId, data)` and `authService.changePassword(oldPassword, newPassword)` documented in endpoint-profile-and-face.md and function-specifications.md.
- **Capabilities matrix expanded:** Added Auth Requirement column, Per-Screen Auth Map table (pre-auth vs post-auth per screen group), updated Readiness Gates with auth verification.
- **Glossary expanded:** From 8 to 16 terms (added Pre-auth endpoint, Post-auth endpoint, Backend-issued JWT, Event envelope, HTTP response envelope, Timezone, Expo SecureStore, Design system constraints).
- **Screen inventory enhanced:** Added Auth column to all screen tables, Screen-to-API Mapping table, Auth Error Handling section (401, close codes 4001/4003).
- **Screen flows enhanced:** Added auth context annotations per flow, registration auth transition, Auth Error Handling section, Timestamp Display note.
- **State matrix expanded:** Added Onboarding Screens column, Auth error (401) and WebSocket close code rows, Auth-Specific State Notes, 7 UX rules.
- **Data model inventory expanded:** Added structured tables with Auth Context column, Backend Data Domains with API endpoint mapping, Mobile File Paths table, Timezone Note.
- **Mobile storage inventory enhanced:** Added Auth Context column, explicit Expo SecureStore requirement, expanded Security Rules (6 rules).
- **Registration draft schema enhanced:** Added Auth Context, structured Field/Type/Source tables per step, auth transition note between Steps 2-3.
- **Module dependency order enhanced:** Structured prerequisite table with "What MOD-09 Needs" column, Auth Dependencies section, expanded Adjacent Modules.
- **Integration points expanded:** Added Auth column to screen files table, expanded service file descriptions (Axios interceptors, JWT query param), structured Backend Contract Providers with auth notes, Auth Integration section, Timezone Integration section.
- **Environment config expanded:** Added `TIMEZONE` variable, Environment-Specific Values table, WebSocket Config section, Security Rules, 6-item Validation Checklist. Removed Supabase URL/Key (mobile doesn't need them).
- **Test strategy expanded:** Added auth flow, timezone, error envelope, design system to scope. Expanded priority areas from 4 to 9.
- **Test cases expanded:** From 6U+6I+4S to **9U+9I+6S**. New unit: T09-U7 (timestamp formatter), T09-U8 (error envelope parser), T09-U9 (SecureStore helper). New integration: T09-I7 (pre-auth endpoint), T09-I8 (post-auth 401), T09-I9 (WS close code 4001). New scenario: T09-S5 (token refresh failure), T09-S6 (timezone display).
- **Demo checklist expanded:** From 8 to **28 items** in 6 categories (Core Functionality, Auth Verification, Data Integrity, Screen State, Connection Reliability, Pass Criteria).
- **Implementation plan expanded:** From 5 to **7 phases** (added Phase 0: Foundations, Phase 6: Validation). Auth enforcement and timezone added to each phase.
- **Task breakdown expanded:** From 6 task groups to **13 tasks** with IDs (MOD9-T00 to MOD9-T12). Added foundations setup, auth verification, and design system compliance to done definition.
- **Folder-file mapping updated:** Added Auth column, expanded service descriptions, fixed canonical docs references.
- **Traceability matrix updated:** Added Auth Type column, new test IDs (T09-U7-U9, T09-I7-I9, T09-S5-S6), auth-specific implementation targets.
- **All files aligned:** Updated governance, catalog, specification, API, data, screen, dependency, testing, implementation, and traceability files for full consistency with main docs, MOD-01, MOD-02, MOD-03, MOD-05, MOD-06, MOD-08.

## 2026-02-07
- Created full Module 9 documentation pack in standardized structure.
- Added student mobile function specifications and acceptance criteria.
- Added consumed API contracts, local-state model, and screen flow/state docs.
- Added testing, implementation plan, AI execution docs, and traceability matrix.
