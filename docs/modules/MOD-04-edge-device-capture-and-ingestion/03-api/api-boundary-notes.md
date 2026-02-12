# API Boundary Notes

## Owned by MOD-04
- `POST /face/process` caller behavior, payload formation, retry/queue handling.
- Edge is the caller; backend is the receiver.

## Auth Boundary
- Edge sends `X-API-Key` header on every request to `/face/process`.
- Backend validates API key via the same middleware used for MOD-03 `POST /face/recognize`.
- Both endpoints share the same `EDGE_API_KEY` env var for validation.
- Edge does NOT use Supabase JWT.

## Related but Owned by Other Modules
- `POST /face/recognize` owned by `MOD-03` — backend internally routes `/face/process` payloads to recognition service. Edge does NOT call `/face/recognize` directly.
- Attendance and presence result handling owned by `MOD-06` and `MOD-07`.

## Backend Orchestration Flow
1. Edge sends cropped faces via `POST /face/process` (owned by MOD-04 as caller).
2. Backend receives payload, resizes crops to 160x160, and internally calls recognition service (MOD-03).
3. Backend updates attendance records (MOD-06) and presence logs (MOD-07).
4. Backend returns processed/matched/unmatched summary to edge.
5. MOD-04 is NOT responsible for recognition or attendance logic — only transmission.

## MOD-02 User Deletion Coordination
When a user is deleted (MOD-02), MOD-03 removes their face registration from FAISS. If edge has queued data containing that user's face, backend will return "unmatched" for that face. No special edge handling is required — edge continues operating normally.

## Coordination Rule
Payload schema changes in backend must be synchronized with edge sender and retry logic before deployment.
