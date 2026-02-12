# Function Specifications

## FUN-03-01 Upload and Validate Face Images
Goal:
- Accept 3-5 face images and validate registration quality rules.

Auth:
- Requires Supabase JWT (student role). User ID extracted from JWT `sub` claim.

Inputs:
- Multipart image files (`images[]`).

Process:
1. Verify Supabase JWT and extract user ID.
2. Validate image count (minimum 3, maximum 5).
3. Validate per-image constraints (face detected, single face, min size).
4. Reject non-compliant uploads with detailed reason.

Outputs:
- Validated image set for embedding generation.

Validation Rules:
- Reject blur/no-face/multiple-face/too-small inputs.
- Reject anonymous registration (must have valid Supabase JWT with active, email-confirmed user).
- User must have `is_active = true` and `email_confirmed_at IS NOT NULL`.

## FUN-03-02 Generate Embeddings
Goal:
- Convert validated face images into model embeddings.

Inputs:
- Validated face image tensors.

Process:
1. Resize images to model input size (160x160 RGB).
2. Normalize image inputs to model requirement.
3. Run FaceNet (InceptionResnetV1) inference.
4. Produce per-image 512-d embeddings.
5. Aggregate embeddings (average) for registration identity vector.

Outputs:
- Embedding vector(s) ready for persistence.

Validation Rules:
- Inference failure returns controlled error.
- Output dimensions must be exactly 512.

## FUN-03-03 Store and Sync Embeddings with FAISS
Goal:
- Persist face registration mapping and keep FAISS index synchronized.

Inputs:
- User ID and embedding vector.

Process:
1. Add/replace embedding in FAISS index.
2. Persist or update `face_registrations` row with embedding mapping.
3. Save FAISS index file to disk.
4. Handle re-registration lifecycle safely (deactivate old mapping, add new).

On User Deletion (triggered by MOD-02):
1. Delete `face_registrations` row for the user.
2. Remove or exclude embedding from FAISS index (rebuild if `IndexFlatIP`).
3. Persist FAISS index to disk.

Outputs:
- Registration metadata with embedding ID and timestamp.

Validation Rules:
- Exactly one active registration per user.
- DB and FAISS operation must be atomic or recoverable.

## FUN-03-04 Recognize Face
Goal:
- Match incoming face crop to registered user embeddings.

Auth:
- Requires API key (`X-API-Key` header) validated against `EDGE_API_KEY` env variable. No Supabase JWT (called by edge devices).

Inputs:
- Face crop image and optional room/context metadata.

Process:
1. Validate API key.
2. Validate face crop.
3. Resize to model input size (160x160 RGB).
4. Generate embedding via FaceNet.
5. Search top-1 neighbor in FAISS.
6. Compare similarity against threshold (default 0.6, from `RECOGNITION_THRESHOLD`).
7. Return matched/unmatched response.

Outputs:
- `matched=true` with user identity and confidence, or `matched=false`.

Validation Rules:
- Recognition threshold sourced from config (`RECOGNITION_THRESHOLD`).
- Unknown/low-confidence faces return unmatched response, not server error.
- Invalid or missing API key returns `401`.

## FUN-03-05 Check Registration Status
Goal:
- Return whether current user has active face registration.

Auth:
- Requires Supabase JWT. User ID extracted from JWT `sub` claim.

Inputs:
- Authenticated user context (from Supabase JWT).

Process:
1. Verify Supabase JWT and extract user ID.
2. Query active face registration record by user.
3. Return registration boolean and timestamp when available.

Outputs:
- Status response with `registered` flag and `registered_at` timestamp.

Validation Rules:
- Missing/invalid Supabase JWT returns `401`.
- Inactive registration should return `registered=false`.
