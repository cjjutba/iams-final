# Business Rules

1. Faculty accounts are pre-seeded in MVP and login-only.
2. Faculty views must show only classes associated with authenticated faculty user.
3. Live attendance screens depend on active class context.
4. Manual attendance updates must be auditable and role-restricted.
5. Early-leave visibility must follow schedule/date filtering.
6. Profile editing must validate input before request submission.
7. Notifications must handle transient websocket disconnect safely.
8. Sensitive auth/session data must not be logged in plaintext.
9. Every API-driven faculty screen includes loading/empty/error states.
10. Upstream API changes require docs updates before code changes.
