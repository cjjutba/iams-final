# Acceptance Criteria

## Function-Level Acceptance

### FUN-03-01
- Given 3-5 valid face images, registration pipeline accepts input.
- Given invalid image set, endpoint returns `400` with reason.

### FUN-03-02
- Given valid face images, embedding generation returns 512-d vectors.
- Given inference failure, endpoint returns controlled error.

### FUN-03-03
- Given valid embedding and user, registration mapping is stored and index persisted.
- Given re-registration, old mapping is handled according to lifecycle policy.

### FUN-03-04
- Given known registered face, endpoint returns `matched=true` and confidence.
- Given unknown face, endpoint returns `matched=false`.

### FUN-03-05
- Given user with active registration, endpoint returns `registered=true`.
- Given user without active registration, endpoint returns `registered=false`.

## Module-Level Acceptance
- DB and FAISS mapping remains consistent after add/update/remove flows.
- Recognition threshold can be adjusted through configuration.
- Registration and re-registration flows align with screen documentation.
