# User and Profile Module Catalog

## Auth Context
All MOD-02 operations require authenticated access via **Supabase JWT**. Role and ownership checks are enforced per function.

## Subdomains
1. User Directory (Admin Scope)
- List user records with role filter and pagination.

2. User Retrieval
- Fetch one user record by ID (admin or own record).

3. Profile Maintenance
- Update editable profile fields (first_name, last_name, phone) with validation and authorization.
- Email is immutable after registration.

4. User Lifecycle Control
- Permanently delete user records with full cleanup (local DB + Supabase Auth + face registrations + FAISS).

## Function Catalog
| Function ID | Name | Summary |
|---|---|---|
| FUN-02-01 | List Users | Return paginated users list (admin scope) |
| FUN-02-02 | Get User | Return one user by ID (admin or own record) |
| FUN-02-03 | Update User | Validate and apply profile updates (first_name, last_name, phone) |
| FUN-02-04 | Delete User | Permanently remove user from local DB and Supabase Auth |

## Actors
- Admin
- Student
- Faculty
- Backend API
- Mobile app profile screens
- Supabase Auth (lifecycle coordination on delete)

## Interfaces
- REST user endpoints (`/users/*`) — protected by Supabase JWT
- Supabase Admin API (`supabase.auth.admin.deleteUser()`) — used on delete
- Database user repository (`users` table)
- Profile screens in mobile client
