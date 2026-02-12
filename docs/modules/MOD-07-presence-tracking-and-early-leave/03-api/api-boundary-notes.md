# API Boundary Notes

## Owned by MOD-07
- Presence logs and early-leave query endpoints (FUN-07-06).
- Internal scan/miss/flag/score service behaviors (FUN-07-01 to FUN-07-05).

## Auth Boundary
- All user-facing endpoints require Supabase JWT with faculty/admin role.
- System-internal functions (FUN-07-01 to FUN-07-05) are invoked by the presence service scan loop — no JWT required.
- Auth middleware shared with MOD-01/MOD-02/MOD-05/MOD-06 (`get_current_user` dependency).

## System-Internal vs User-Facing Functions
- **System-Internal (FUN-07-01 to FUN-07-05):** No HTTP endpoints. Invoked by the presence service scan loop running as a background job (APScheduler).
- **User-Facing (FUN-07-06):** Exposed as GET /presence/* HTTP endpoints. Requires Supabase JWT with faculty or admin role.

## Related but Owned by Other Modules
- **MOD-02:** User deletion cascades to attendance_records → presence_logs + early_leave_events.
- **MOD-03/MOD-04:** Recognition pipeline provides detection results that feed MOD-07 scan evaluation.
- **MOD-05:** Schedule and enrollment data provide session context (schedule boundaries, enrolled students).
- **MOD-06:** Attendance row creation/update. MOD-07 updates attendance status (present → early_leave).
- **MOD-08:** WebSocket event delivery for early-leave alerts to mobile clients.

## Coordination Rules
- Changes to threshold/session behavior must be synchronized with attendance status updates (MOD-06) and realtime alert payloads (MOD-08).
- Response envelope must follow project standard: `{ "success": true, "data": {}, "message": "" }` for success; `{ "success": false, "error": { "code": "", "message": "" } }` for errors.
