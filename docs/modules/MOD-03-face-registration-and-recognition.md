# MOD-03: Face Registration and Recognition

This file is a module-level source of truth derived from `docs/main/master-blueprint.md` section 6.
Update both files together when module scope changes.

## Specification

Purpose:
- Register student face embeddings and identify faces during class.

Functions:
- `FUN-03-01`: Upload and validate 3-5 face images.
- `FUN-03-02`: Generate embeddings.
- `FUN-03-03`: Store and sync embeddings with FAISS.
- `FUN-03-04`: Recognize faces using similarity threshold.
- `FUN-03-05`: Check whether user already has registered face.

API Contracts:
- `POST /face/register`
- `POST /face/recognize`
- `GET /face/status`

Data:
- `face_registrations`
- `users`
- Local FAISS index file

Screens:
- `SCR-009` StudentRegisterStep3Screen
- `SCR-017` StudentFaceReregisterScreen
- `SCR-030` CameraScreen

Done Criteria:
- Reject invalid images (blur, no face, multiple faces, too small).
- Embeddings remain consistent between DB and FAISS.
- Recognition threshold is configurable.


## Implementation Rule
- Implement only the listed `FUN-*` items for this module when this doc is referenced.
- If scope/API/data/screen changes are needed, update docs first before code.
