# Face Screen Flows

## Student Registration Step 3 Flow
1. Open `SCR-009` (user must be authenticated with Supabase JWT from earlier registration steps).
2. Capture 3-5 face angles using `SCR-030`.
3. Validate images locally/basic checks.
4. Submit to `POST /face/register` with Supabase JWT in `Authorization` header.
5. On success, proceed with registration completion flow.

## Face Re-registration Flow
1. Open `SCR-017` (user must be authenticated with Supabase JWT).
2. Check current status via `GET /face/status` (Supabase JWT).
3. Capture new image set with `SCR-030`.
4. Submit to `POST /face/register` as replacement (Supabase JWT).
5. Confirm new registration timestamp/status.

## Recognition Flow Context
- Edge/integration path uses `POST /face/recognize` with API key (`X-API-Key`); no direct student UI for this endpoint.
- Backend resizes incoming crops to 160x160 before FaceNet inference.
