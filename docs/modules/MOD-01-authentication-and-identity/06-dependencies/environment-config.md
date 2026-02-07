# Environment Configuration

## Required Variables (Auth Context)
- JWT secret/public key config
- Access token expiry minutes
- Refresh token policy settings
- Database connection settings
- Supabase URL/key (if Supabase auth mode is used)

## Configuration Rules
- Never hardcode secrets in source code.
- Keep `.env.example` synchronized with runtime requirements.
- Production must use secure transport (`https`) and production-grade secrets.

## Validation Checklist
- App starts with complete env configuration.
- Missing env values fail fast with clear errors.
- Auth endpoints operate with configured token expiry.
