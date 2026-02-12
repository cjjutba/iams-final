# Changelog (MOD-08)

## 2026-02-12
- **Canonical sources fixed:** Removed `master-blueprint.md`, `technical-specification.md`, `testing.md`, `folder-structure.md`, `screen-list.md`. Added `architecture.md`, `implementation.md`, `database-schema.md`, `prd.md` in README.md and folder-file-mapping.md.
- **Auth context added:** New Auth Context sections in README.md, goal-and-objectives.md, working-rules.md, realtime-catalog.md, module-specification.md, capabilities-matrix.md. Explicit user-facing (FUN-08-01, FUN-08-05) vs system-internal (FUN-08-02 to FUN-08-04) distinction throughout.
- **Auth rules added:** New Auth Rules section in working-rules.md and business-rules.md. WebSocket endpoint requires Supabase JWT via `token` query param. Close code 4001 (Unauthorized) and 4003 (Forbidden). All roles can connect. System-internal functions (FUN-08-02/03/04) need no JWT.
- **Timezone rules documented:** Added Timezone Rules section in working-rules.md and business-rules.md. Added `TIMEZONE` env var to environment-config.md. All event timestamps use ISO-8601 with +08:00 offset.
- **Environment config expanded:** From 5+4 variables to structured tables with shared (5), backend-specific (4), and mobile-specific (4) variables. Added `TIMEZONE`, Configuration Rules, Security Rules (JWT redaction in logs), 7-item Validation Checklist.
- **Capabilities matrix expanded:** Added Auth Requirement column, Per-Role Access table (student/faculty/admin), Auth Note section. Added SCR-025 to connection screens.
- **Glossary expanded:** From 8 to 14 terms (added Supabase JWT, Close code 4001, Close code 4003, System-internal function, Notification service, Timezone).
- **Function specifications enhanced:** Added Function Categories header, Type/Auth/Caller Context per function, specific input types (UUID, ISO-8601), detailed process steps with close codes, JSON response examples.
- **Endpoint contract expanded:** Added Query Params table (`token`), detailed Auth Requirement section, Connection Lifecycle (10 steps), realistic JSON with 2026-aligned dates and +08:00 offsets, Close/Error Cases table with close codes.
- **Event contracts enhanced:** Added Caller Context (which module calls, when), Timezone Note, realistic JSON examples with 2026-02-12 dates and +08:00 offsets, schedule_id as required field in attendance_update, Optional Fields tables, Dedup Rule in early_leave.
- **Error models expanded:** Added WebSocket Close Codes table (4001/4003/1000/1011), structured Handshake/Auth Errors with close codes, HTTP Error Response Shape note (no `details` array), Error Scenarios by Function table (11 scenarios), timestamp in observability fields.
- **API boundary notes expanded:** Added Auth Boundary, System-Internal vs User-Facing section, Input Contracts table, Related Modules table (7 modules), Payload Evolution and Versioning strategy (additive-only for MVP), Coordination Rules.
- **Connection lifecycle model enhanced:** Added Auth Context (JWT validation before map entry), Transition Rules table, Reconnect Rules (idempotent, one socket per user), Heartbeat Behavior section with env var references.
- **Data model inventory expanded:** Added structured tables for primary data, consumed data, Backend File Paths, Cross-Module Data Flow table, MOD-02 User Deletion Impact, Data Lifecycle (5 stages).
- **Event payload schema enhanced:** Added Timezone Note, realistic JSON with 2026 dates and +08:00 offsets, structured required/optional fields per event, expanded Validation Rules (timezone offset, status values, additive-only).
- **Screen inventory expanded:** Added Auth column, SCR-025 FacultyEarlyLeaveAlertsScreen, Screen-to-Function Mapping table, Auth Error Handling section (4001/4003).
- **State matrix expanded:** Added SCR-025 column, Auth Error (4001) and Permission Error (4003) rows, 7 UX rules (pull-to-refresh, reconnecting badge, auth handling, backoff, timestamp display).
- **Screen flows enhanced:** Added auth context per flow, SCR-025 flow, Auth Error Handling section (4001→login redirect, 4003→error message), exponential backoff details.
- **Module dependency order expanded:** From 3 to 5 prerequisites (added MOD-02 lifecycle, MOD-05 schedule/enrollment), structured tables with specific descriptions.
- **Integration points expanded:** Added Auth Integration, Backend File Paths table (6 files), Mobile File Paths table (6 files), Cross-Module Integration table (7 modules), Timezone Integration.
- **Test strategy expanded:** Added auth validation, timezone formatting, error handling to scope. Expanded priority areas from 4 to 9.
- **Test cases expanded:** From 6U+5I+4S to **9U+8I+5S**. New unit: T08-U7 (missing token), T08-U8 (expired JWT), T08-U9 (unknown event type). New integration: T08-I6 (reconnect evict stale), T08-I7 (timezone offset), T08-I8 (student routing).
- **Demo checklist expanded:** From 8 to **28 items** organized in 6 categories (Core Functionality, Auth Verification, Connection Reliability, Data Integrity, Screen Integration, Error Handling).
- **Implementation plan expanded:** From 5 to **6 phases** (added Phase 0: Foundations for auth/trigger/env verification).
- **Task breakdown expanded:** From 5 groups to **11 tasks** with task IDs (MOD8-T00 to MOD8-T10), added foundations setup and auth verification tasks. Auth enforcement and timezone added to done definition.
- **Folder-file mapping updated:** Added schemas/websocket.py, notificationStore.ts, SCR-025 screen file. Fixed canonical docs references.
- **Traceability matrix updated:** Added new test IDs (T08-U7, T08-U8, T08-U9, T08-I6, T08-I7, T08-I8, T08-S5), system-internal labels, auth-specific implementation targets for FUN-08-01. Added SCR-025 to screen mappings.
- **All files aligned:** Updated governance, catalog, specification, API, data, screen, dependency, testing, implementation, and traceability files for full consistency with main docs, MOD-01, MOD-02, MOD-03, MOD-04, MOD-05, MOD-06, and MOD-07.

## 2026-02-07
- Created full Module 8 documentation pack using standardized folder structure.
- Added endpoint and event-level API contracts for websocket notifications.
- Added connection lifecycle, payload schema, and optional delivery-log models.
- Added testing strategy, task breakdown, AI runbook, and traceability matrix.
