# Business Rules

1. Student flow uses only student-allowed APIs and data.
2. Registration requires successful ID verification before account creation.
3. Registration requires valid face upload before final submission.
4. Student mobile must not expose faculty/admin-only controls.
5. Authenticated screens require active session or explicit re-auth flow.
6. Session tokens are stored only in secure mobile storage.
7. Sensitive fields are never written to plaintext logs.
8. Data-driven screens implement loading/empty/error states.
9. Notification UI should tolerate transient websocket failures.
10. Contract changes across APIs require docs-first updates.
