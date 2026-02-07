# Acceptance Criteria

## Function-Level Acceptance

### FUN-02-01
- Given admin token and valid query params, endpoint returns paginated users list.
- Given non-admin token, endpoint returns `403`.

### FUN-02-02
- Given valid user ID and authorized caller, endpoint returns user profile.
- Given unknown ID, endpoint returns `404`.
- Given unauthorized caller, endpoint returns `403`.

### FUN-02-03
- Given valid payload and authorized caller, endpoint updates and returns profile data.
- Given restricted/invalid fields, endpoint returns validation error.
- Given unauthorized caller, endpoint returns `403`.

### FUN-02-04
- Given authorized admin and existing user, endpoint performs delete/deactivate successfully.
- Given unknown ID, endpoint returns `404`.
- Given unauthorized caller, endpoint returns `403`.

## Module-Level Acceptance
- Profile endpoints and screens remain consistent.
- Role-based controls are enforced across all user endpoints.
- Delete/deactivate behavior is documented and does not break related modules.
