# Module Dependency Order

## Upstream Dependencies for MOD-03
1. `MOD-01` Authentication and Identity
- Required for Supabase JWT middleware on student-facing endpoints.
- Required for user identity context (JWT `sub` claim = user ID).

2. `MOD-02` User and Profile Management
- MOD-02 user deletion triggers face data cleanup in MOD-03.
- MOD-03 must expose a service method for face data deletion.

3. `MOD-11` Data Import and Seed Operations
- Required for initial user dataset readiness.

4. Supabase Project Setup
- Supabase Auth configured and JWT secret available.
- Database connection established.

## MOD-03 Before/After Sequence
1. Implement `MOD-01` baseline auth (Supabase JWT middleware).
2. Implement `MOD-02` user management (for deletion coordination).
3. Implement `MOD-03` face registration/recognition core.
4. Integrate with:
- `MOD-04` edge capture and process contract (shared API key auth)
- `MOD-06` attendance marking workflows

## Internal Function Dependency Order
1. `FUN-03-01` Upload and validate images
2. `FUN-03-02` Generate embeddings
3. `FUN-03-03` Store and sync embeddings
4. `FUN-03-05` Check registration status
5. `FUN-03-04` Recognize face

## Rationale
- Registration pipeline must be stable before recognition is trusted in attendance flows.
- Auth middleware (MOD-01) must be in place before any protected endpoint works.
- User deletion coordination (MOD-02) should be implemented alongside or shortly after MOD-03 core.
