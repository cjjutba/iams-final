# Changelog (MOD-03 Docs)

## 2026-02-12
- **Supabase Auth alignment:** Student-facing endpoints (`POST /face/register`, `GET /face/status`) now explicitly reference Supabase JWT authentication (aligned with MOD-01).
- **API key auth for edge:** Recognition endpoint (`POST /face/recognize`) uses shared API key (`X-API-Key` header, validated against `EDGE_API_KEY` env variable) since edge devices (RPi) don't hold Supabase JWTs.
- **Backend resize responsibility:** Documented that backend handles resizing incoming face crops to 160x160 (FaceNet model input) — edge devices send crops at detection output size.
- **MOD-02 deletion coordination:** Added face data cleanup on user deletion — MOD-02 triggers `delete_face_data_for_user(user_id)` which removes face_registrations row and FAISS entry.
- **FAISS lifecycle updated:** Remove operation now explicitly references MOD-02 user deletion as trigger. Cross-module coordination section added.
- **Canonical sources fixed:** Replaced stale references (master-blueprint.md, technical-specification.md, testing.md) with correct files (architecture.md, implementation.md, database-schema.md).
- **Response envelope updated:** Added optional `message` field to success envelope for consistency with MOD-01/MOD-02.
- **Environment config expanded:** Added `EDGE_API_KEY`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, `FACENET_MODEL_PATH` to required variables.
- **Auth error codes added:** Added `FORBIDDEN` (403) for inactive/unconfirmed users. Error scenarios documented per function.
- **Test cases expanded:** Added auth tests (JWT, API key, expired, missing), deletion cleanup tests, resize tests. Expanded from 6 unit + 6 integration + 4 E2E to 9 unit + 12 integration + 6 E2E.
- **Demo checklist expanded:** Added auth verification items, deletion cleanup, resize verification. Expanded from 8 to 15 items.
- **Task breakdown updated:** Expanded from 8 to 10 tasks with API key middleware setup and MOD-02 deletion coordination tasks.
- **Glossary expanded:** Added Supabase JWT, API Key (Edge Auth), FaceNet, Model Input Resize definitions.
- **"5 angles" corrected:** Fixed main implementation.md to say "3-5 angles" (was incorrectly "5 angles").
- **Timestamps fixed:** Updated example timestamps from 2024 to 2026.
- **All files aligned:** Updated governance, catalog, specification, API, data, screen, dependency, testing, implementation, and traceability files for full consistency with main docs, MOD-01, and MOD-02.

## 2026-02-07
- Created full Module 3 documentation pack under `docs/modules/MOD-03-face-registration-and-recognition/`.
- Added governance, catalog, specifications, API contracts, data docs, screen docs, dependencies, testing, implementation, AI execution, and traceability files.
