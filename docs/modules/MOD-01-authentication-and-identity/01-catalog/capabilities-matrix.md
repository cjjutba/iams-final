# Capabilities Matrix

| Actor | Capability | Function ID(s) | Notes |
|---|---|---|---|
| Student | Verify identity by student ID | FUN-01-01 | Required before registration; backend endpoint |
| Student | Register new account | FUN-01-02 | Only after valid identity check; backend creates Supabase Auth user + local DB |
| Student | Login | FUN-01-03 | Via Supabase client SDK (`signInWithPassword`) |
| Student | Refresh session | FUN-01-04 | Via Supabase client SDK (automatic) |
| Student | Fetch own profile | FUN-01-05 | Requires valid Supabase JWT; backend endpoint |
| Student | Request password reset | FUN-01-06 | Via Supabase client SDK (`resetPasswordForEmail`) |
| Student | Complete password reset | FUN-01-07 | Via Supabase client SDK (`updateUser`) |
| Faculty | Login | FUN-01-03 | Faculty is pre-seeded in MVP; Supabase client SDK |
| Faculty | Refresh session | FUN-01-04 | Same Supabase client behavior as student |
| Faculty | Fetch own profile | FUN-01-05 | Role in response should be faculty |
| Faculty | Request password reset | FUN-01-06 | Via Supabase client SDK |
| Faculty | Complete password reset | FUN-01-07 | Via Supabase client SDK |
| Backend | Verify Supabase JWT on protected routes | FUN-01-03, FUN-01-05 | Enforced via auth middleware |
| Backend | Create Supabase Auth user on registration | FUN-01-02 | Via Supabase Admin API |
| Backend | Enforce email_confirmed and is_active | FUN-01-05 | Checked on every protected route |
| Ops/Admin | Seed faculty accounts | External dependency | Not a direct MOD-01 endpoint |
