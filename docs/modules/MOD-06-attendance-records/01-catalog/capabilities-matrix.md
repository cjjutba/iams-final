# Capabilities Matrix

| Actor | Capability | Function ID(s) | Auth Requirement | Notes |
|---|---|---|---|---|
| Backend recognition flow | mark attendance from recognized user | FUN-06-01 | system/internal | dedup by student_id+schedule_id+date |
| Faculty | view today's class attendance | FUN-06-02 | Supabase JWT + faculty role | class context (schedule_id) required |
| Admin | view today's class attendance | FUN-06-02 | Supabase JWT + admin role | full access to any schedule |
| Student | view own attendance history | FUN-06-03 | Supabase JWT + student role | own records only (JWT sub scoped) |
| Faculty | view own class attendance history | FUN-06-03 | Supabase JWT + faculty role | own classes (faculty_id match) |
| Faculty | view attendance history by filters | FUN-06-04 | Supabase JWT + faculty role | schedule/date filters |
| Admin | view attendance history by filters | FUN-06-04 | Supabase JWT + admin role | unrestricted schedule access |
| Faculty | manual attendance update | FUN-06-05 | Supabase JWT + faculty role | remarks + audit required |
| Admin | manual attendance update | FUN-06-05 | Supabase JWT + admin role | remarks + audit required |
| Faculty | live class roster monitoring | FUN-06-06 | Supabase JWT + faculty role | active session context |
| Admin | live class roster monitoring | FUN-06-06 | Supabase JWT + admin role | active session context |

## Auth Note
- All user-facing capabilities require Supabase JWT. Missing/invalid JWT → 401. Insufficient role → 403.
- FUN-06-01 (Mark Attendance) is a system operation triggered by the recognition pipeline, not a user-facing endpoint.
- No API key auth — that pattern is for MOD-03/MOD-04 edge devices only.
