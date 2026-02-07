# Faculty Mobile Catalog

## Module Summary
- Module ID: `MOD-10`
- Module Name: Faculty Mobile App
- Primary Domain: Mobile

## Function Catalog
| Function ID | Function Name | Brief Description |
|---|---|---|
| FUN-10-01 | Faculty login and session restore | Authenticate faculty users and restore active session safely. |
| FUN-10-02 | View schedule and active class | Present teaching schedule and active class context. |
| FUN-10-03 | Live attendance monitoring | Display realtime attendance roster and scan updates. |
| FUN-10-04 | Manual attendance updates | Allow faculty correction/override of attendance records. |
| FUN-10-05 | Early-leave alerts and class summaries | Show in-session alerts and post-session class summary views. |
| FUN-10-06 | Faculty profile and notifications | Manage profile details and view notification feed. |

## Screen Domains
- Auth: `SCR-005`, `SCR-006`
- Faculty portal: `SCR-019` to `SCR-029`

## API Domain
Module 10 consumes APIs from auth, schedules, attendance, presence, user profile, and websocket modules.
