# Module Specification

## Module ID
`MOD-03`

## Purpose
Register student face embeddings and identify faces during class.

## Auth Context
- Student-facing endpoints (`POST /face/register`, `GET /face/status`) are protected by Supabase JWT middleware from MOD-01.
- Edge-facing endpoint (`POST /face/recognize`) is protected by shared API key (`X-API-Key` header).

## Core Functions
- `FUN-03-01`: Upload and validate 3-5 face images (Supabase JWT required).
- `FUN-03-02`: Generate 512-d embeddings (FaceNet, 160x160 input; backend resizes).
- `FUN-03-03`: Store and sync embeddings with FAISS; handle MOD-02 deletion cleanup.
- `FUN-03-04`: Recognize faces using similarity threshold (API key auth).
- `FUN-03-05`: Check whether user already has registered face (Supabase JWT required).

## API Contracts
- `POST /face/register` — Supabase JWT auth
- `POST /face/recognize` — API key auth (`X-API-Key`)
- `GET /face/status` — Supabase JWT auth

## Data Dependencies
- `face_registrations`
- `users` (identity linkage; MOD-02 deletion triggers cleanup)
- Local FAISS index file
- Supabase Auth (user identity context from MOD-01)

## Screen Dependencies
- `SCR-009` StudentRegisterStep3Screen
- `SCR-017` StudentFaceReregisterScreen
- `SCR-030` CameraScreen

## Done Criteria
- Reject invalid images (blur, no face, multiple faces, too small).
- Embeddings remain consistent between DB and FAISS.
- Recognition threshold is configurable.
- Supabase JWT enforced on register and status endpoints.
- API key enforced on recognize endpoint.
- User deletion (MOD-02) correctly cleans up face_registrations and FAISS entry.
