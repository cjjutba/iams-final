# User and Profile Module Catalog

## Subdomains
1. User Directory (Admin Scope)
- List user records with role filter and pagination.

2. User Retrieval
- Fetch one user record by ID.

3. Profile Maintenance
- Update profile fields with validation and authorization.

4. User Lifecycle Control
- Delete or deactivate user records safely.

## Function Catalog
| Function ID | Name | Summary |
|---|---|---|
| FUN-02-01 | List Users | Return paginated users list (admin scope) |
| FUN-02-02 | Get User | Return one user by ID |
| FUN-02-03 | Update User | Validate and apply profile updates |
| FUN-02-04 | Delete/Deactivate User | Remove or deactivate a user safely |

## Actors
- Admin
- Student
- Faculty
- Backend API
- Mobile app profile screens

## Interfaces
- REST user endpoints (`/users/*`)
- Database user repository (`users` table)
- Profile screens in mobile client
