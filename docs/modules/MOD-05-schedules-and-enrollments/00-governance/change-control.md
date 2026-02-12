# Change Control

## What Requires Change Control
- Schedule endpoint request/response changes.
- Time semantics or active schedule rules changes.
- Enrollment relationship/constraint changes.
- Access policy changes for schedule APIs.

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
