# Function Specifications

## FUN-03-01 Upload and Validate Face Images
Goal:
- Accept 3-5 face images and validate registration quality rules.

Inputs:
- Multipart image files (`images[]`).

Process:
1. Validate image count (minimum 3, maximum 5).
2. Validate per-image constraints (face detected, single face, min size).
3. Reject non-compliant uploads with detailed reason.

Outputs:
- Validated image set for embedding generation.

Validation Rules:
- Reject blur/no-face/multiple-face/too-small inputs.
- Reject anonymous registration (must be authenticated user context where applicable).

## FUN-03-02 Generate Embeddings
Goal:
- Convert validated face images into model embeddings.

Inputs:
- Validated face image tensors.

Process:
1. Normalize/resize image inputs to model requirement.
2. Run FaceNet inference.
3. Produce per-image 512-d embeddings.
4. Aggregate embeddings (for example average) for registration identity vector.

Outputs:
- Embedding vector(s) ready for persistence.

Validation Rules:
- Inference failure returns controlled error.
- Output dimensions must match expected size.

## FUN-03-03 Store and Sync Embeddings with FAISS
Goal:
- Persist face registration mapping and keep FAISS index synchronized.

Inputs:
- User ID and embedding vector.

Process:
1. Add/replace embedding in FAISS index.
2. Persist or update `face_registrations` row with embedding mapping.
3. Save FAISS index file to disk.
4. Handle re-registration lifecycle safely.

Outputs:
- Registration metadata with embedding ID and timestamp.

Validation Rules:
- Exactly one active registration per user.
- DB and FAISS operation must be atomic or recoverable.

## FUN-03-04 Recognize Face
Goal:
- Match incoming face crop to registered user embeddings.

Inputs:
- Face crop image and optional room/context metadata.

Process:
1. Validate face crop.
2. Generate embedding.
3. Search top-1 neighbor in FAISS.
4. Compare similarity against threshold.
5. Return matched/unmatched response.

Outputs:
- `matched=true` with user identity and confidence, or `matched=false`.

Validation Rules:
- Recognition threshold sourced from config.
- Unknown/low-confidence faces return unmatched response, not server error.

## FUN-03-05 Check Registration Status
Goal:
- Return whether current user has active face registration.

Inputs:
- Authenticated user context.

Process:
1. Query active face registration record by user.
2. Return registration boolean and timestamp when available.

Outputs:
- Status response with `registered` flag.

Validation Rules:
- Missing user context returns auth error.
- Inactive registration should return `registered=false`.
