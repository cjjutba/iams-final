# Endpoint Contract: Registration Flow

## Scope
Endpoints used in student registration flow.

## Endpoints
- `POST /auth/verify-student-id`
- `POST /auth/register`
- `POST /face/register`

## Step Mapping
- Step 1 (`SCR-007`): verify student identity.
- Step 2 (`SCR-008`): collect account details for registration payload.
- Step 3 (`SCR-009`): upload 3-5 face images.
- Step 4 (`SCR-010`): review and submit final registration.

## Validation Rules
- `verify-student-id` must return `valid: true` before continuing.
- Face upload must satisfy image quality and count constraints.
- Final submit blocked until required steps are complete.
