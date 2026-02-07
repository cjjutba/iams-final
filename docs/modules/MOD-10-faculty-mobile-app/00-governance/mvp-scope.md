# MVP Scope

## In Scope
- `FUN-10-01`: Faculty login and session restore.
- `FUN-10-02`: View schedule and active class.
- `FUN-10-03`: Live attendance monitoring.
- `FUN-10-04`: Manual attendance updates.
- `FUN-10-05`: View early-leave alerts and class summaries.
- `FUN-10-06`: Faculty profile and notifications.

## Screen Scope
- Auth: `SCR-005`, `SCR-006`
- Faculty portal: `SCR-019`, `SCR-020`, `SCR-021`, `SCR-022`, `SCR-023`, `SCR-024`, `SCR-025`, `SCR-026`, `SCR-027`, `SCR-028`, `SCR-029`

## Out of Scope
- Faculty self-registration or invite code flows.
- Full admin reporting suite beyond module screens.
- Push-provider integration outside websocket path.

## Scope Dependencies
- Auth contracts from `MOD-01`.
- Schedule data from `MOD-05`.
- Attendance and manual entry from `MOD-06`.
- Early-leave data from `MOD-07`.
- Realtime transport from `MOD-08`.
