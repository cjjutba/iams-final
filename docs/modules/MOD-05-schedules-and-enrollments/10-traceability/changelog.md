# Changelog (MOD-05 Docs)

## 2026-02-12
- **Canonical sources fixed:** Removed `master-blueprint.md`, `technical-specification.md`, `testing.md`, `screen-list.md`. Added `architecture.md`, `implementation.md`, `database-schema.md` in README.md and folder-file-mapping.md.
- **Auth rules added:** New Auth Rules section in working-rules.md and business-rules.md. All endpoints require Supabase JWT. POST /schedules requires admin role. No API key auth (that pattern is for MOD-03/MOD-04 edge devices).
- **Response envelope updated:** Added `message` field to all success responses for consistency with MOD-01/MOD-02/MOD-03/MOD-04 envelope format.
- **Role-based access control documented:** Explicit auth requirements per endpoint in api-inventory.md, all endpoint contracts, function-specifications.md, and acceptance-criteria.md. Includes 401 (missing JWT), 403 (non-admin/unauthorized), and roster access control.
- **Roster access control specified:** GET /schedules/{id}/students restricted to admin, assigned faculty (faculty_id match), or enrolled students (enrollment record check). Documented in function-specifications.md, endpoint-get-schedule-students.md, and business-rules.md.
- **Timezone configuration documented:** Added Timezone Rules section in working-rules.md and business-rules.md. Configured via `TIMEZONE` env var (default: Asia/Manila for JRMSU pilot). TIME type columns interpreted in configured timezone. Added to environment-config.md, schedule-session-semantics.md.
- **day_of_week mapping documented:** Added explicit 0-6 mapping table (0=Sunday through 6=Saturday) in schedules-table-fields.md, glossary.md, endpoint contracts, and function-specifications.md.
- **Active schedule semantics expanded:** Clarified "current class" detection algorithm in schedule-session-semantics.md (is_active + day_of_week + time window). Added query semantics section.
- **Enrollment lifecycle documented:** Added rules for cascade deletion (student removal), schedule deactivation (enrollments preserved), and no soft delete on enrollments. Documented in business-rules.md, enrollments-and-rooms-fields.md, data-model-inventory.md.
- **Enrollment scope note added:** Documented that MVP has no direct enrollment API. Enrollments managed by MOD-11 import scripts. Added to module-specification.md, api-boundary-notes.md, mvp-scope.md.
- **MOD-04 edge device integration documented:** Added rooms→schedules→current class mapping documentation in integration-points.md, api-boundary-notes.md, data-model-inventory.md, and schedule-session-semantics.md.
- **MOD-02 user deletion coordination added:** Documented cascade deletion of enrollments when student is deleted. Added to api-boundary-notes.md, data-model-inventory.md, business-rules.md.
- **Cross-module coordination section added:** New section in module-specification.md covering MOD-04, MOD-06, MOD-07, MOD-11, and MOD-02 coordination.
- **Query parameters expanded:** GET /schedules now documents `day`, `room_id`, `faculty_id`, `active_only` query params. Added to endpoint-list-schedules.md, function-specifications.md.
- **Roster response fields documented:** Response includes `id` (users.id), `student_id` (users.student_id), `first_name`, `last_name`. Updated student_id example from "2024-0001" to "21-A-012345" to match seed data format. Documented in endpoint-get-schedule-students.md.
- **Error models enhanced:** Removed `details` array from error shape. Added Error Code column to status mapping. Added Error Scenarios by Function table.
- **Environment config expanded:** From 3 generic variables to 5 specific variables in table format (DATABASE_URL, SUPABASE_URL, SUPABASE_ANON_KEY, JWT_SECRET_KEY, TIMEZONE). Added security rules and validation checklist.
- **Screen state matrix expanded:** Added Auth Error (401) and Permission Error (403) columns. Added pull-to-refresh and auth error handling to UX rules.
- **Test cases expanded:** From 5U+8I+4E to **8U+13I+5E**. New tests: T05-U6 (invalid day_of_week), T05-U7 (non-faculty faculty_id), T05-U8 (non-existent room_id), T05-I9 (unassigned faculty roster access), T05-I10 (enrolled student roster access), T05-I11 (non-enrolled student roster access), T05-I12 (missing JWT on POST), T05-I13 (missing JWT on GET /me), T05-E5 (expired JWT redirect).
- **Demo checklist expanded:** From 8 to **24 items** organized by category (Core Functionality, Auth Verification, Access Control, Data Integrity, Screen Integration, Timezone).
- **Implementation plan expanded:** From 5 to **6 phases**. Added Phase 1 (Foundations) for auth middleware verification, model validation, and timezone config.
- **Task breakdown expanded:** From 8 to **10 tasks**. Added MOD5-T01 (foundations setup) and MOD5-T09 (roster access control verification).
- **Folder-file mapping expanded:** Added model files (schedule.py, enrollment.py, room.py), auth dependency (dependencies.py). Fixed canonical docs references.
- **Traceability matrix updated:** Added new test IDs (T05-U6-U8, T05-I9-I13, T05-E5) and auth-specific implementation targets for all 5 functions.
- **All files aligned:** Updated governance, catalog, specification, API, data, screen, dependency, testing, implementation, and traceability files for full consistency with main docs, MOD-01, MOD-02, MOD-03, and MOD-04.

## 2026-02-07
- Created full Module 5 documentation pack under `docs/modules/MOD-05-schedules-and-enrollments/`.
- Added governance, catalog, specifications, API contracts, data docs, screen docs, dependencies, testing, implementation, AI execution, and traceability files.
