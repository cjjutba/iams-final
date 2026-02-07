# Environment Configuration

## Required Variables (Schedule Context)
- Database connection settings
- Auth/JWT verification settings
- Server timezone configuration (if explicit)

## Configuration Rules
- Timezone assumptions must be explicit and consistent.
- Missing auth/db config should fail fast.
- Query behavior should be deterministic across environments.

## Validation Checklist
- Schedules endpoints available with valid config.
- Day/time filters behave consistently.
- Role-based schedule access checks are enabled.
