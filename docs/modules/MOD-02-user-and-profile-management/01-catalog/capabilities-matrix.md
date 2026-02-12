# Capabilities Matrix

| Actor | Capability | Function ID(s) | Notes |
|---|---|---|---|
| Admin | List users with filter and pagination | FUN-02-01 | Admin scope only |
| Admin | Get any user by ID | FUN-02-02 | Admin scope |
| Admin | Update any user's editable fields | FUN-02-03 | first_name, last_name, phone |
| Admin | Permanently delete user | FUN-02-04 | Deletes from local DB + Supabase Auth + face registrations |
| Student | View own profile | FUN-02-02 | Scoped to own record |
| Student | Update own editable fields | FUN-02-03 | first_name, last_name, phone only; email immutable |
| Faculty | View own profile | FUN-02-02 | Scoped to own record |
| Faculty | Update own editable fields | FUN-02-03 | first_name, last_name, phone only; email immutable |
| Backend | Enforce role access via Supabase JWT middleware | FUN-02-01..FUN-02-04 | Middleware from MOD-01 |
| Backend | Coordinate Supabase Auth deletion on user delete | FUN-02-04 | Via Supabase Admin API |
