# Environment Configuration

## Required Variables (Presence Context)
- `SCAN_INTERVAL`
- `EARLY_LEAVE_THRESHOLD`
- timezone/session boundary settings (if explicit)
- database and auth settings

## Configuration Rules
- Threshold and interval must be configurable per deployment.
- Invalid threshold config should fail fast.
- Session timing assumptions should be explicit.

## Validation Checklist
- Presence worker starts with valid config.
- Scan interval and threshold are logged at startup (non-secret).
- Early-leave behavior reflects configured values.
