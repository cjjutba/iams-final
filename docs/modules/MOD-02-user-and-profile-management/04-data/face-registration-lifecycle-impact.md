# Face Registration Lifecycle Impact

## Related Table
`face_registrations`

## Impact Scenarios
1. User deactivated
- Expected behavior: linked face registration should be treated inactive or ignored by recognition flow.

2. User hard deleted
- Expected behavior: linked face registration row must be deleted or remapped safely.
- FAISS cleanup/rebuild strategy must be coordinated with `MOD-03`.

## Policy Recommendation for MVP
- Prefer soft delete (`is_active=false`) in `users`.
- Keep lifecycle consistency by marking or handling linked face records.

## Cross-Module Coordination
- `MOD-02` (lifecycle action) and `MOD-03` (face registry/index) must remain synchronized.
