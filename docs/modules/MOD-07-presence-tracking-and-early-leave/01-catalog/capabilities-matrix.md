# Capabilities Matrix

| Actor | Capability | Function ID(s) | Auth Requirement | Notes |
|---|---|---|---|---|
| Presence service | start session context | FUN-07-01 | system-internal (no JWT) | schedule/date scoped, uses TIMEZONE |
| Presence service | execute periodic scan | FUN-07-02 | system-internal (no JWT) | default 60s interval |
| Presence service | update miss counters | FUN-07-03 | system-internal (no JWT) | per-student state, deterministic |
| Presence service | flag early leave | FUN-07-04 | system-internal (no JWT) | threshold based (default: 3) |
| Presence service | compute score | FUN-07-05 | system-internal (no JWT) | scans_detected / total_scans |
| Faculty | view presence logs | FUN-07-06 | Supabase JWT (faculty role) | class detail views (SCR-023) |
| Faculty | view early-leave events | FUN-07-06 | Supabase JWT (faculty role) | alerts/detail views (SCR-025) |
| Admin | view presence logs | FUN-07-06 | Supabase JWT (admin role) | unrestricted access |
| Admin | view early-leave events | FUN-07-06 | Supabase JWT (admin role) | unrestricted access |
| Student | view presence logs | — | — | no direct access (403); see attendance via MOD-06 |
| Student | view early-leave events | — | — | no direct access (403); notified via MOD-08 |

## Auth Note
- FUN-07-01 to FUN-07-05 are system-internal — no HTTP endpoints, no JWT required.
- FUN-07-06 is the only user-facing function — requires Supabase JWT with faculty or admin role.
- Students cannot access MOD-07 endpoints directly. They receive attendance status via MOD-06 and alerts via MOD-08.
- 401 for missing/invalid JWT; 403 for insufficient role.
- No API key auth (that pattern is for MOD-03/MOD-04 edge devices only).
