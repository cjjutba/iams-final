# Face Screen Flows

## Student Registration Step 3 Flow
1. Open `SCR-009`.
2. Capture 3-5 face angles using `SCR-030`.
3. Validate images locally/basic checks.
4. Submit to `POST /face/register`.
5. On success, proceed with registration completion flow.

## Face Re-registration Flow
1. Open `SCR-017`.
2. Check current status via `GET /face/status`.
3. Capture new image set with `SCR-030`.
4. Submit to `POST /face/register` as replacement.
5. Confirm new registration timestamp/status.

## Recognition Flow Context
- Edge/integration path uses `POST /face/recognize`; no direct student UI for this endpoint.
