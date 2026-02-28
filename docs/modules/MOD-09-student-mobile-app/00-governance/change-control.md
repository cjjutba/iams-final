# Change Control

## Changes Requiring Documentation Update First
- Registration step order, validation rules, or required fields.
- Authentication/session storage behavior.
- Student screen additions/removals/renames.
- Consumed API path, payload, or auth requirements.
- Notification event handling behavior on student screens.

## Required Update Targets
- `02-specification/` for behavior changes
- `03-api/` for endpoint and payload changes
- `05-screens/` for UI and flow impacts
- `10-traceability/traceability-matrix.md`

## Decision Log Policy
If conflicts exist across docs, add a dated note in `10-traceability/changelog.md` before implementation proceeds.
