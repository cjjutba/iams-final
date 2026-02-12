# Changelog (MOD-07 Docs)

## 2026-02-12
- **Canonical sources fixed:** Removed `master-blueprint.md`, `technical-specification.md`, `testing.md`, `screen-list.md`. Added `architecture.md`, `implementation.md`, `database-schema.md`, `prd.md` in README.md and folder-file-mapping.md.
- **Auth context added:** New Auth Context sections in README.md, goal-and-objectives.md, working-rules.md, presence-catalog.md, module-specification.md. Explicit system-internal vs user-facing function distinction throughout.
- **Auth rules added:** New Auth Rules section in working-rules.md and business-rules.md. FUN-07-06 endpoints require Supabase JWT with faculty/admin role. FUN-07-01 to FUN-07-05 are system-internal (no JWT). 401/403 responses documented.
- **System-internal vs user-facing documented:** Clear distinction that FUN-07-01 to FUN-07-05 are service-layer functions (no HTTP endpoints) and FUN-07-06 is the only user-facing API function. Documented in function-specifications.md, api-boundary-notes.md, capabilities-matrix.md.
- **Response envelope updated:** Added `message` field to all success responses. Removed `details` array from error shape for consistency with MOD-01 through MOD-06 envelope format.
- **Timezone rules documented:** Added Timezone Rules section in working-rules.md and business-rules.md. Added TIMEZONE env var to environment-config.md, state-and-threshold-model.md. Session boundaries use configured timezone.
- **Environment config expanded:** From vague bullets to 7-variable table (DATABASE_URL, SUPABASE_URL, SUPABASE_ANON_KEY, JWT_SECRET_KEY, SCAN_INTERVAL, EARLY_LEAVE_THRESHOLD, TIMEZONE). Added Security Rules and 7-item Validation Checklist.
- **Role requirements column added:** Added Auth Requirement column to capabilities-matrix.md (expanded from 7 to 11 rows including all 3 roles). Added Auth column to screen-inventory.md.
- **Endpoint contracts expanded:** Added Auth Requirement, Path/Query Parameters tables, Timezone Notes, structured Error Cases tables, realistic JSON examples with 2026-aligned dates and `+08:00` offsets to both endpoint docs.
- **Error models updated:** Removed `details` array. Added Error Code table and Error Scenarios by Function table (10 scenarios across both endpoints).
- **Cross-module coordination added:** New Cross-Module Data Flow table and MOD-02 User Deletion Impact section in data-model-inventory.md. New Cross-Module Integration table (7 modules) in integration-points.md. Added Downstream Consumers section in module-dependency-order.md.
- **Screen state matrix expanded:** Added Auth Error (401) and Permission Error (403) columns. Added pull-to-refresh and auth error handling UX rules.
- **Test cases expanded:** From 6U+5I+4S to **8U+10I+5S**. New unit: T07-U7 (zero scans), T07-U8 (invalid schedule). New integration: T07-I6 (missing JWT logs), T07-I7 (missing JWT early-leaves), T07-I8 (student JWT logs), T07-I9 (expired JWT logs), T07-I10 (expired JWT early-leaves). New scenario: T07-S5 (auth redirect).
- **Demo checklist expanded:** From 8 to **25 items** organized by 6 categories (Core Functionality, Auth Verification, Access Control, Data Integrity, Screen Integration, Timezone).
- **Implementation plan expanded:** From 5 to **7 phases** (added Phase 0: Foundations and Phase 5: Mobile Integration).
- **Task breakdown expanded:** From 9 to **11 tasks** (added MOD7-T00 foundations setup and MOD7-T09 auth enforcement verification).
- **Folder-file mapping expanded:** Added model files (presence_log.py, early_leave_event.py), auth dependency (dependencies.py), tracking service, Zustand store. Fixed canonical docs references.
- **Field docs enhanced:** Added Schema Alignment notes, Timezone Notes, Foreign Key Relationships tables, Dedup Rules to both presence-logs-fields.md and early-leave-events-fields.md.
- **State model enhanced:** Converted to table format. Added Default Threshold Parameters table with env vars. Added Recovery Behavior and Edge Cases sections.
- **Glossary expanded:** From 6 to 12 terms (added Presence Log, Supabase JWT, System-Internal Function, Timezone, Attendance Record, Cascade Deletion).
- **Traceability matrix updated:** Added new test IDs (T07-U7, T07-U8, T07-I6-I10, T07-S5) and auth-specific implementation targets for FUN-07-06.
- **All files aligned:** Updated governance, catalog, specification, API, data, screen, dependency, testing, implementation, and traceability files for full consistency with main docs, MOD-01, MOD-02, MOD-03, MOD-04, MOD-05, and MOD-06.

## 2026-02-07
- Created full Module 7 documentation pack under `docs/modules/MOD-07-presence-tracking-and-early-leave/`.
- Added governance, catalog, specifications, API contracts, data docs, screen docs, dependencies, testing, implementation, AI execution, and traceability files.
