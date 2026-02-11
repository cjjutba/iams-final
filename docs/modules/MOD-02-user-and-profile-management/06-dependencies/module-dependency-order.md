# Module Dependency Order

## Upstream Dependencies for MOD-02
1. `MOD-01` Authentication and Identity
- Required for Supabase JWT middleware, role enforcement, and user context.
2. Supabase project setup
- Required for Supabase Admin API access (used in delete operations).

## MOD-02 Before/After Sequence
1. Implement `MOD-01` auth baseline (Supabase JWT middleware, user creation).
2. Implement `MOD-02` user/profile endpoints.
3. Then integrate dependent screens in:
- `MOD-09` Student mobile app
- `MOD-10` Faculty mobile app

## Internal Function Dependency Order
1. `FUN-02-02` Get user by ID (foundation for profile screens)
2. `FUN-02-03` Update user profile (depends on get for pre-fill)
3. `FUN-02-01` List users (admin — independent of profile screens)
4. `FUN-02-04` Delete user (requires Supabase Admin API + MOD-03 FAISS coordination)

## Rationale
- Profile screens need read/update flow first.
- Admin list/delete can be added once core retrieval/update paths are stable.
- Delete requires both Supabase Admin API integration and MOD-03 FAISS coordination.
