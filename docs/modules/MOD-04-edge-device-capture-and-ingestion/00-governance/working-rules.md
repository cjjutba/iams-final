# Working Rules

## Source-of-Truth Rules
1. This folder is the implementation reference for `MOD-04`.
2. If implementation needs behavior not documented here, update docs first.
3. If docs conflict, create an ADR and resolve before coding.
4. Every implementation task must reference `MOD-04` and at least one `FUN-04-*` ID.

## Auth Rules
1. Edge device authenticates with backend using a shared API key in the `X-API-Key` header.
2. The API key is read from the `EDGE_API_KEY` environment variable on both edge and backend.
3. Edge devices do NOT use Supabase JWT — JWT is for student/faculty-facing endpoints only (MOD-01).
4. Backend validates the API key on `POST /face/process` and returns 401 on missing/invalid key.

## Scope Control
- Implement only `FUN-04-01` to `FUN-04-05` under this module.
- Do not move recognition, attendance, or presence decision logic into edge pipeline.
- Edge crops faces at ~112x112; backend handles resize to 160x160 for FaceNet model input.

## Quality Rules
- Edge payloads must match `POST /face/process` contract.
- Every request must include `X-API-Key` header.
- Queue policy bounds must be enforced (`max_size: 500`, `TTL: 5 min`, `retry_interval: 10s`).
- Retry loop must not halt capture pipeline.
- Operational logs must include queue depth and send failures.

## Delivery Rules
- Each commit/PR should include traceability, for example:
  - `Implements MOD-04 FUN-04-04`
- Any API contract change must update:
  - `03-api/api-inventory.md`
  - relevant endpoint file(s)
  - `10-traceability/traceability-matrix.md`

## Change Process
1. Propose doc updates.
2. Review consistency across API/data/testing docs.
3. Implement code.
4. Run tests.
5. Update traceability and changelog.
