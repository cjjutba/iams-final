# Module Dependency Order

## Upstream Dependencies for MOD-03
1. `MOD-01` Authentication and Identity
- Required for user context and protected registration status flow.

2. `MOD-11` Data Import and Seed Operations
- Required for initial user dataset readiness.

## MOD-03 Before/After Sequence
1. Implement `MOD-01` baseline auth.
2. Implement `MOD-03` face registration/recognition core.
3. Integrate with:
- `MOD-04` edge capture and process contract
- `MOD-06` attendance marking workflows

## Internal Function Dependency Order
1. `FUN-03-01` Upload and validate images
2. `FUN-03-02` Generate embeddings
3. `FUN-03-03` Store and sync embeddings
4. `FUN-03-05` Check registration status
5. `FUN-03-04` Recognize face

## Rationale
- Registration pipeline must be stable before recognition is trusted in attendance flows.
