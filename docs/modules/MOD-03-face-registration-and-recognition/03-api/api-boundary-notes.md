# API Boundary Notes

## Owned by MOD-03
- `POST /face/register` — Supabase JWT auth (student-facing)
- `POST /face/recognize` — API key auth (edge-facing)
- `GET /face/status` — Supabase JWT auth (student-facing)

## Related but Owned by Other Module
- `POST /face/process` is owned by `MOD-04` (Edge Device Capture and Ingestion). Also uses API key auth.

## Auth Boundary
- Supabase JWT middleware (from MOD-01) is used for student-facing endpoints. MOD-03 does not implement its own JWT verification — it reuses MOD-01's middleware.
- API key validation for edge endpoints is implemented in MOD-03 (or shared with MOD-04). The key is stored in `EDGE_API_KEY` env variable.

## Coordination Rule
- Changes to `POST /face/process` payload that affect recognition extraction must be reflected in MOD-03 integration docs and tests.
- MOD-02 user deletion triggers face data cleanup in MOD-03 (face_registrations + FAISS). MOD-03 exposes a service method for this.
