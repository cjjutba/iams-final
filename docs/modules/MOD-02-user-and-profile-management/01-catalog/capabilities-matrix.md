# Capabilities Matrix

| Actor | Capability | Function ID(s) | Notes |
|---|---|---|---|
| Admin | List users with filter and pagination | FUN-02-01 | Admin scope only |
| Admin | Get any user by ID | FUN-02-02 | Admin scope only |
| Admin | Update user record | FUN-02-03 | Depending on policy |
| Admin | Delete/deactivate user | FUN-02-04 | Must preserve integrity |
| Student | View own profile | FUN-02-02 | Scoped to own record unless admin |
| Student | Update own editable fields | FUN-02-03 | Restricted field set |
| Faculty | View own profile | FUN-02-02 | Scoped to own record unless admin |
| Faculty | Update own editable fields | FUN-02-03 | Restricted field set |
| Backend | Enforce role access and field-level validation | FUN-02-01..FUN-02-04 | Via dependencies/middleware |
