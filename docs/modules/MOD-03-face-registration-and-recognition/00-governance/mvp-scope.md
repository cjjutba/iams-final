# MVP Scope

## In Scope
- Face registration upload and validation (3-5 images).
- Embedding generation and storage.
- Recognition endpoint for incoming face crops.
- Registration status endpoint.
- FAISS/DB synchronization lifecycle documentation.

## Out of Scope
- Custom model training.
- Liveness detection beyond baseline validation checks.
- Large-scale multi-index sharding.

## MVP Constraints
- Recognition model: FaceNet (InceptionResnetV1).
- Embedding size: 512 dimensions.
- Match threshold default: 0.6 (configurable).
- One active face registration per user.

## MVP Gate Criteria
- `FUN-03-01` through `FUN-03-05` implemented and tested.
- Invalid image inputs are blocked.
- Recognition matched/unmatched behavior works as documented.
- FAISS and `face_registrations` synchronization is validated.
