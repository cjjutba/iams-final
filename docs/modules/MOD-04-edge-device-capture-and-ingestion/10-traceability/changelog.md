# Changelog (MOD-04 Docs)

## 2026-02-12
- **API key auth established:** Edge device authenticates with backend via shared API key (`X-API-Key` header, validated against `EDGE_API_KEY` env var). Replaced vague "depends on deployment policy" with explicit auth requirement across all files.
- **Auth rules added:** New Auth Rules section in working-rules.md and business-rules.md. Edge does NOT use Supabase JWT.
- **Auth failure handling documented:** 401 responses are logged and NOT queued for retry (config issue, not transient). Added to runtime flow, state matrix, and acceptance criteria.
- **Crop size boundary clarified:** Edge crops at ~112x112 (MediaPipe detection output). Backend handles resize to 160x160 for FaceNet model input. Added Resize Boundary section to FUN-04-02 and across all relevant files.
- **Canonical sources fixed:** Replaced stale references (`master-blueprint.md`, `technical-specification.md`, `testing.md`) with correct files (`architecture.md`, `implementation.md`, `database-schema.md`) in README.md and folder-file-mapping.md.
- **Response envelope updated:** Added optional `message` field to success response for consistency with MOD-01/MOD-02/MOD-03 envelope format.
- **Timestamps fixed:** Updated example timestamps from 2024 to 2026 in endpoint-process-frame.md.
- **Environment config expanded:** Expanded from 4 generic variables to 9 specific variables in table format. Added `EDGE_API_KEY` as required variable with security rules (never commit to source control, never log value).
- **MediaPipe configuration documented:** Added MediaPipe Face Detector section in integration-points.md with model variant, input/output, confidence threshold, and platform details.
- **Backend orchestration flow documented:** Added Backend Orchestration Flow section in api-boundary-notes.md explaining: edge sends to `/face/process` → backend resizes → backend calls recognition (MOD-03) → backend updates attendance (MOD-06/MOD-07).
- **MOD-02 user deletion coordination added:** Documented graceful handling — if user is deleted while edge has queued data, backend returns "unmatched". No special edge handling needed.
- **MOD-06/MOD-07 downstream integration documented:** Added data flow explanation in integration-points.md showing how `/face/process` response feeds into attendance and presence tracking.
- **Idempotency note added:** Documented that edge may retry same payload multiple times; backend should handle gracefully. Added to FUN-04-05 and queue-policy-model.md.
- **Queue policy terminology fixed:** Separated queue parameters from send policy. `batch_size` moved to Send Policy table.
- **Test cases expanded:** From 6U + 4I + 3S to **8U + 7I + 4S**. Added API key auth tests (T04-U7, T04-I5, T04-I6), crop size verification (T04-U8), deleted user handling (T04-I7), and auth failure scenario (T04-S4).
- **Demo checklist expanded:** From 8 to **15 items**. Added API key verification, auth failure behavior, crop size boundary, and EDGE_API_KEY logging check.
- **Task breakdown expanded:** From 7 to **9 tasks**. Added MOD4-T01 (env + API key setup) and MOD4-T07 (auth failure handling).
- **Implementation plan expanded:** From 5 to **6 phases**. Added Phase 1 (Foundations) for env config and API key setup.
- **Traceability matrix updated:** Added new test IDs (T04-U7, T04-U8, T04-I5, T04-I6, T04-I7, T04-S4) and auth-specific implementation targets.
- **Logging updated:** Added auth failure logging, 401 response tracking, and EDGE_API_KEY non-logging rule.
- **All files aligned:** Updated governance, catalog, specification, API, data, screen/runtime, dependency, testing, implementation, and traceability files for full consistency with main docs, MOD-01, MOD-02, and MOD-03.

## 2026-02-07
- Created full Module 4 documentation pack under `docs/modules/MOD-04-edge-device-capture-and-ingestion/`.
- Added governance, catalog, specifications, API contracts, data docs, runtime notes, dependencies, testing, implementation, AI execution, and traceability files.
