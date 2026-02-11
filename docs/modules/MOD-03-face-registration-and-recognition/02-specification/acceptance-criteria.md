# Acceptance Criteria

## Function-Level Acceptance

### FUN-03-01
- Given 3-5 valid face images with valid Supabase JWT, registration pipeline accepts input.
- Given invalid image set, endpoint returns `400` with reason.
- Given missing/invalid Supabase JWT, endpoint returns `401`.
- Given inactive or unconfirmed user, endpoint returns `403`.

### FUN-03-02
- Given valid face images, embedding generation returns 512-d vectors.
- Given inference failure, endpoint returns controlled error.
- Backend resizes images to 160x160 before model inference.

### FUN-03-03
- Given valid embedding and user, registration mapping is stored and index persisted.
- Given re-registration, old mapping is handled according to lifecycle policy.
- Given user deletion (MOD-02 trigger), face_registrations row and FAISS entry are removed.

### FUN-03-04
- Given known registered face with valid API key, endpoint returns `matched=true` and confidence.
- Given unknown face with valid API key, endpoint returns `matched=false`.
- Given missing/invalid API key, endpoint returns `401`.
- Backend resizes incoming crop to 160x160 before recognition.

### FUN-03-05
- Given user with active registration and valid Supabase JWT, endpoint returns `registered=true` with timestamp.
- Given user without active registration and valid Supabase JWT, endpoint returns `registered=false`.
- Given missing/invalid Supabase JWT, endpoint returns `401`.

## Module-Level Acceptance
- DB and FAISS mapping remains consistent after add/update/remove flows.
- Recognition threshold can be adjusted through configuration (`RECOGNITION_THRESHOLD`).
- Registration and re-registration flows align with screen documentation.
- Supabase JWT enforced on student-facing endpoints; API key enforced on edge-facing endpoint.
- User deletion from MOD-02 correctly cleans up face data.
