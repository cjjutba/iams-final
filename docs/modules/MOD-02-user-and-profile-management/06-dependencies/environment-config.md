# Environment Configuration

## Required Variables (User/Profile Context)
- Database connection settings
- Auth/JWT verification settings
- API base configuration
- Logging level and audit log destination (if configured)

## Configuration Rules
- Never hardcode secrets in source code.
- Keep `.env.example` synchronized with runtime requirements.
- Protected user endpoints must fail closed on missing auth config.

## Validation Checklist
- User endpoints start successfully with complete config.
- Authorization checks are active in non-local environments.
- Profile update validation behaves consistently across environments.
