# Environment Configuration

## Required Variables (Attendance Context)
- Database connection settings
- Auth/JWT verification settings
- timezone configuration (if explicit)
- optional grace period/session config values

## Configuration Rules
- Time/date interpretation must be consistent.
- Missing auth/db config should fail fast.
- Attendance status constants should be centrally defined.

## Validation Checklist
- Attendance endpoints boot with valid config.
- Date range filters and today queries use consistent timezone.
- Role authorization is active.
