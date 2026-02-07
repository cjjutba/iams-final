# Business Rules

## Registration Rules
1. Student face registration requires 3-5 valid images.
2. One active face registration per user.
3. Re-registration replaces or deactivates previous active embedding mapping.

## Recognition Rules
1. Recognition uses configured threshold (default 0.6).
2. If score is below threshold, result must be `matched=false`.
3. Recognition response must always follow documented payload shape.

## Persistence Rules
1. `face_registrations` and FAISS index must remain synchronized.
2. On remove/deactivate, FAISS mapping must be updated or rebuild strategy applied.
3. FAISS index file must be persisted after write operations.

## Security Rules
1. Face embeddings are not reversible to original image.
2. Raw registration images should be minimized or handled per storage policy.
3. Endpoint access policies must align with role/auth constraints.
