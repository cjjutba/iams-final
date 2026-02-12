# Changelog (MOD-10)

## 2026-02-12
- **Canonical sources fixed:** Removed `master-blueprint.md`, `technical-specification.md`, `screen-list.md`. Added `architecture.md`, `implementation.md`, `database-schema.md`, `prd.md` in README.md and folder-file-mapping.md.
- **Auth context added:** New Auth Context sections in README.md, goal-and-objectives.md, module-specification.md, faculty-mobile-catalog.md, capabilities-matrix.md. Explicit pre-auth (SCR-005, SCR-006) vs post-auth (SCR-019 to SCR-029) distinction throughout.
- **Auth rules added:** New Auth Rules section in working-rules.md and business-rules.md. Pre-auth endpoints (login, forgot-password) require no JWT. Post-auth endpoints require `Authorization: Bearer <token>`. WebSocket uses JWT via `token` query param.
- **Token architecture documented:** New Token Architecture section in mvp-scope.md. Backend-issued JWT (not Supabase client SDK). Stored in Expo SecureStore. Axios interceptors for auto-attach and 401 refresh. WebSocket uses query param for JWT.
- **Timezone rules documented:** Added Timezone Rules in working-rules.md, mvp-scope.md, environment-config.md. ISO-8601 with +08:00 offset (Asia/Manila). YYYY-MM-DD date filters. `TIMEZONE` env var added.
- **Design system constraints documented:** New Design System Constraints section in mvp-scope.md. Text weight types, Avatar styling, Divider spacing, colors.status limits, snake_case API fields.
- **Error envelope shape documented:** Added HTTP Response Envelope and explicit "no `details` array" note in error-models.md, api-inventory.md, api-boundary-notes.md, glossary.md, business-rules.md, acceptance-criteria.md.
- **WebSocket close codes documented:** Added close codes table (4001/4003/1000/1011) in endpoint-faculty-notifications.md, error-models.md. Client handling: 4001 → login redirect, 4003 → error message.
- **Pre-auth vs post-auth API table added:** New consolidated table in api-boundary-notes.md listing all 14 endpoints with auth status.
- **Endpoint contracts enhanced:** Added Auth column, request/response examples with 2026 dates and +08:00 offsets in all endpoint files.
- **Service method notes added:** `authService.updateProfile(userId, data)` and `authService.changePassword(oldPassword, newPassword)` documented in function-specifications.md and acceptance-criteria.md.
- **Capabilities matrix expanded:** Added Auth Requirement column, Per-Screen Auth Map table, updated Readiness Gates with auth verification.
- **Glossary expanded:** From 8 to 16 terms (added Pre-auth endpoint, Post-auth endpoint, Backend-issued JWT, Event envelope, HTTP response envelope, Timezone, Expo SecureStore, Design system constraints).
- **Screen inventory enhanced:** Added Auth column to all screen tables, Screen-to-API Mapping table, Auth Error Handling section (401, close codes 4001/4003).
- **Screen name fixed:** Corrected `FacultyEarlyLeaveAlertsScreen` → `FacultyAlertsScreen` to match actual implementation file.
- **Screen flows enhanced:** Added auth context annotations per flow, Auth Error Handling section, Timestamp Display note.
- **State matrix expanded:** Added Auth Screens column, Auth error (401) and WebSocket close code (4001/4003) rows, Auth-Specific State Notes, 7 UX rules.
- **Data model inventory expanded:** Added Auth Context column, Backend Data Domains with API endpoint mapping, Mobile File Paths table, Timezone Note.
- **Mobile local state model expanded:** Added Auth Context column, Auth Store TypeScript interface, Storage Strategy table (SecureStore vs AsyncStorage).
- **Mobile storage inventory enhanced:** Added Auth Context column, split into SecureStore vs AsyncStorage, expanded Security Rules (6 rules).
- **Faculty live-class state schema:** Updated timestamps to 2026 dates with +08:00 offset. Added colors.status note.
- **Manual attendance payload schema:** Updated date to 2026, added Auth Context, Response Envelope section with "no details array" note.
- **Module dependency order enhanced:** Structured table with "What MOD-10 Needs" column, Auth Dependencies section.
- **Integration points expanded:** Added Auth column to screen files, expanded service descriptions (Axios interceptors, JWT query param), Auth Integration section, Timezone Integration section.
- **Environment config expanded:** Added `TIMEZONE` variable, Environment-Specific Values table, WebSocket Config section, Security Rules, 6-item Validation Checklist. Added note that mobile does not need Supabase URL/Key.
- **Stakeholders table added:** 8 stakeholders in goal-and-objectives.md.
- **Cross-module dependencies table added:** 6 modules with auth notes in module-specification.md.
- **Test strategy expanded:** Added auth, timezone, error envelope, design system to scope. 9 priority areas.
- **Test cases expanded:** From 6U+6I+5S (17) to **9U+9I+7S (25 total)**. New unit: T10-U7 (timestamp formatter), T10-U8 (error envelope parser), T10-U9 (SecureStore helper). New integration: T10-I7 (pre-auth endpoint), T10-I8 (post-auth 401), T10-I9 (WS close code 4001). New scenario: T10-S6 (reconnect), T10-S7 (timezone display).
- **Demo checklist expanded:** From 9 to **31 items** in 6 categories (Pre-Demo Setup, Core Functionality, Auth Verification, Data Integrity, Screen State Verification, Connection Reliability, Pass Criteria).
- **Implementation plan expanded:** From 5 to **7 phases** (added Phase 0: Foundations, Phase 5: Hardening, Phase 6: Validation). Auth enforcement and timezone added to each phase.
- **Task breakdown expanded:** From 5 task groups to **14 tasks** with IDs (MOD10-T00 to MOD10-T13). Added foundations setup, auth verification, and docs tasks. Done definition expanded with auth, timezone, error envelope, design system requirements.
- **Traceability matrix enhanced:** Added Auth Type column, new test IDs (T10-U7-U9, T10-I7-I9, T10-S5-S7), auth-specific implementation targets.
- **All files aligned:** Updated governance, catalog, specification, API, data, screen, dependency, testing, implementation, and traceability files for full consistency with main docs, MOD-01 through MOD-09.

## 2026-02-07
- Created full Module 10 documentation pack in standardized structure.
- Added faculty mobile function specifications and acceptance criteria.
- Added consumed API contracts for schedule/live/manual/alerts/notifications.
- Added local state, screen flows, testing, implementation, AI execution, and traceability docs.
