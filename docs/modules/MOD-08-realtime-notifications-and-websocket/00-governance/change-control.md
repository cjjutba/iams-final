# Change Control

## Changes Requiring Documentation Update First
- Any new or renamed WebSocket event type.
- Any payload field add/remove/rename in event contracts.
- Any auth handshake or `user_id` validation behavior change.
- Any reconnect/backoff strategy change exposed to mobile.

## Required Update Targets
- `03-api/` for endpoint/event contracts
- `04-data/` for payload and connection models
- `05-screens/` for UI-state impacts
- `10-traceability/traceability-matrix.md`

## Decision Log Policy
If behavior is uncertain or conflicts across docs, add a dated entry in `10-traceability/changelog.md` before implementation proceeds.
