# MOD-10: Faculty Mobile App

This file is a module-level source of truth derived from `docs/main/master-blueprint.md` section 6.
Update both files together when module scope changes.

## Specification

Purpose:
- Give faculty live visibility and control for class attendance.

Functions:
- `FUN-10-01`: Faculty login and session restore.
- `FUN-10-02`: View schedule and active class.
- `FUN-10-03`: Live attendance monitoring.
- `FUN-10-04`: Manual attendance updates.
- `FUN-10-05`: View early-leave alerts and class summaries.
- `FUN-10-06`: Faculty profile and notifications.

Screens:
- Auth: `SCR-005`, `SCR-006`
- Faculty portal: `SCR-019`, `SCR-020`, `SCR-021`, `SCR-022`, `SCR-023`, `SCR-024`, `SCR-025`, `SCR-026`, `SCR-027`, `SCR-028`, `SCR-029`

Done Criteria:
- Faculty can monitor a live class end-to-end.
- Manual entry updates are reflected in live/history views.
- Alert screens show realtime events.


## Implementation Rule
- Implement only the listed `FUN-*` items for this module when this doc is referenced.
- If scope/API/data/screen changes are needed, update docs first before code.
