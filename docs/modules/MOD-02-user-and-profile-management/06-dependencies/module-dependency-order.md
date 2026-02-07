# Module Dependency Order

## Upstream Dependencies for MOD-02
1. `MOD-01` Authentication and Identity
- Required for token/auth context and role enforcement.

## MOD-02 Before/After Sequence
1. Implement `MOD-01` auth baseline.
2. Implement `MOD-02` user/profile endpoints.
3. Then integrate dependent screens in:
- `MOD-09` Student mobile app
- `MOD-10` Faculty mobile app

## Internal Function Dependency Order
1. `FUN-02-02` Get user by ID
2. `FUN-02-03` Update user profile
3. `FUN-02-01` List users (admin)
4. `FUN-02-04` Delete/deactivate user

## Rationale
- Profile screens need read/update flow first.
- Admin list/delete can be added once core retrieval/update paths are stable.
