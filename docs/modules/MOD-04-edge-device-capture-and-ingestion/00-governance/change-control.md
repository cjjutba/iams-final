# Change Control

## What Requires Change Control
- Edge API payload schema changes.
- Queue max size/TTL/retry policy changes.
- Recovery behavior changes (camera disconnect, crash restart).
- Time budget/resource limit assumptions.

## Change Workflow
1. Update impacted docs in this module pack.
2. Link impacted canonical docs in `docs/main/`.
3. Record change in `10-traceability/changelog.md`.
4. Execute implementation and tests.
5. Update traceability matrix.

## Versioning Convention
- Major: breaking API/pipeline changes.
- Minor: added compatible fields/behaviors.
- Patch: clarifications and non-behavior doc fixes.
