# MVP Scope

## In Scope
- `FUN-09-01`: Onboarding and welcome flow.
- `FUN-09-02`: Student login and token persistence.
- `FUN-09-03`: Four-step registration flow:
  - Step 1 identity verification
  - Step 2 account setup
  - Step 3 face registration
  - Step 4 review and submit
- `FUN-09-04`: Student home, schedule, attendance history/detail.
- `FUN-09-05`: Profile view/edit and face re-registration.
- `FUN-09-06`: Student notifications (including realtime integration path).

## Out of Scope
- Faculty mobile features (`MOD-10`).
- Admin operations.
- Offline-first full registration/auth.
- Push notification provider integration (FCM/APNs).

## Scope Dependencies
- Auth backend contracts from `MOD-01`.
- Face registration contracts from `MOD-03`.
- Schedule and attendance data from `MOD-05` and `MOD-06`.
- Realtime transport contracts from `MOD-08`.
