# Changelog (MOD-06 Docs)

## 2026-02-12
- **Canonical sources fixed:** Removed `master-blueprint.md`, `technical-specification.md`, `testing.md`, `screen-list.md`. Added `architecture.md`, `implementation.md`, `database-schema.md`, `prd.md` in README.md and folder-file-mapping.md.
- **Auth rules added:** New Auth Rules section in working-rules.md and business-rules.md. All user-facing endpoints require Supabase JWT. FUN-06-02/04/05/06 require faculty/admin role. FUN-06-03 is role-scoped. No API key auth (that pattern is for MOD-03/MOD-04 edge devices).
- **Response envelope updated:** Added `message` field to all success responses. Removed `details` array from error shape for consistency with MOD-01-05 envelope format.
- **Role-based access control documented:** Explicit auth requirements per endpoint in api-inventory.md, all endpoint contracts, function-specifications.md, and acceptance-criteria.md. Includes 401 (missing JWT), 403 (insufficient role), and schedule ownership access control.
- **Schedule ownership access control specified:** GET /attendance (FUN-06-04) restricted to faculty assigned to the schedule (faculty_id match) or admin. Documented in function-specifications.md, endpoint-get-attendance-history.md, and business-rules.md.
- **Timezone rules documented:** Added Timezone Rules section in working-rules.md and business-rules.md. Configured via `TIMEZONE` env var (default: Asia/Manila for JRMSU pilot). "Today" queries use configured timezone, not UTC.
- **Missing fields added:** Added `remarks`, `updated_by` columns to attendance-records-fields.md (existed in database-schema.md but were missing from MOD-06 field docs).
- **Status transitions documented:** Added Status Transitions section to status-summary-definitions.md (present→early_leave via MOD-07, manual override by faculty).
- **Manual override policy expanded:** Added Supabase JWT role requirement, required `remarks`, `updated_by`/`updated_at` auto-population, status validation to dedup-and-manual-override-policy.md.
- **Cross-module data flow added:** New Cross-Module Data Flow table in data-model-inventory.md (MOD-03→06, MOD-05→06, MOD-06→07, MOD-06→08). Added MOD-02 User Deletion Impact and Data Lifecycle sections.
- **Environment config expanded:** From vague bullets to 5 specific variables in table format (DATABASE_URL, SUPABASE_URL, SUPABASE_ANON_KEY, JWT_SECRET_KEY, TIMEZONE). Added Security Rules and expanded Validation Checklist (7 items).
- **Screen state matrix expanded:** Added Auth Error (401) and Permission Error (403) columns. Added pull-to-refresh and auth error handling to UX rules.
- **Test cases expanded:** From 5U+7I+4E to **8U+13I+5E**. New tests: T06-U6 (missing remarks), T06-U7 (invalid date range), T06-U8 (unknown student_id), T06-I8 (missing JWT on today), T06-I9 (student JWT on today), T06-I10 (unassigned faculty history), T06-I11 (missing JWT on manual), T06-I12 (student JWT on live), T06-I13 (expired JWT).
- **Demo checklist expanded:** From 8 to **28 items** organized by 6 categories (Core Functionality, Auth Verification, Access Control, Data Integrity, Screen Integration, Timezone).
- **Implementation plan expanded:** From 5 to **6 phases** (added Phase 1: Foundations for auth middleware verification, model validation, and timezone config).
- **Task breakdown expanded:** From 9 to **11 tasks** (added MOD6-T01 foundations setup and MOD6-T10 auth enforcement verification).
- **Folder-file mapping expanded:** Added model file (attendance_record.py), auth dependency (dependencies.py), Zustand store (attendanceStore.ts). Fixed canonical docs references.
- **Traceability matrix updated:** Added new test IDs (T06-U6-U8, T06-I8-I13, T06-E5) and auth-specific implementation targets for all 6 functions.
- **All files aligned:** Updated governance, catalog, specification, API, data, screen, dependency, testing, implementation, and traceability files for full consistency with main docs, MOD-01, MOD-02, MOD-03, MOD-04, and MOD-05.

## 2026-02-07
- Created full Module 6 documentation pack under `docs/modules/MOD-06-attendance-records/`.
- Added governance, catalog, specifications, API contracts, data docs, screen docs, dependencies, testing, implementation, AI execution, and traceability files.
