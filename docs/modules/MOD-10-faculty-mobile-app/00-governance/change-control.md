# Change Control

## Changes Requiring Documentation Update First
- Faculty login/session behavior changes.
- Live attendance UI behavior or payload assumptions.
- Manual attendance payload or flow changes.
- Early-leave/summary display logic changes.
- Faculty screen additions/removals/renames.

## Required Update Targets
- `02-specification/` for behavior changes
- `03-api/` for endpoint and payload changes
- `05-screens/` for UI/flow impacts
- `10-traceability/traceability-matrix.md`

## Decision Log Policy
If docs conflict or behavior is unclear, add a dated note in `10-traceability/changelog.md` before implementation proceeds.
