# Capabilities Matrix

| Actor | Capability | Function ID(s) | Notes |
|---|---|---|---|
| Student | Verify identity by student ID | FUN-01-01 | Required before registration |
| Student | Register new account | FUN-01-02 | Only after valid identity check |
| Student | Login | FUN-01-03 | Uses student credentials |
| Student | Refresh session | FUN-01-04 | Keeps session alive |
| Student | Fetch own profile | FUN-01-05 | Requires valid bearer token |
| Faculty | Login | FUN-01-03 | Faculty is pre-seeded in MVP |
| Faculty | Refresh session | FUN-01-04 | Same token behavior as student |
| Faculty | Fetch own profile | FUN-01-05 | Role in response should be faculty |
| Backend | Verify token on protected routes | FUN-01-03, FUN-01-04, FUN-01-05 | Enforced via auth dependency middleware |
| Ops/Admin | Seed faculty accounts | External dependency | Not a direct MOD-01 endpoint |
