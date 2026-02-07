# Change Control

## What Requires Change Control
- User endpoint path, request, or response changes.
- Allowed profile fields or validation rule changes.
- Delete/deactivate semantics changes.
- Role access policy changes for user endpoints.
- Schema changes affecting user profile fields.

## Change Workflow
1. Update impacted docs in this module pack.
2. Link impacted canonical docs in `docs/main/`.
3. Record change in `10-traceability/changelog.md`.
4. Execute implementation and tests.
5. Update traceability matrix.

## Versioning Convention
- Major: breaking API/behavior changes.
- Minor: added compatible fields/flows.
- Patch: clarifications and non-behavior doc fixes.
