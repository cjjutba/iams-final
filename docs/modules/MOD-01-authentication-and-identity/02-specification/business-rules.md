# Business Rules

## Registration Rules
1. Student registration requires successful identity verification first.
2. Student ID must match university-provided dataset.
3. Email and student_id must be unique in user store.
4. Faculty cannot self-register in MVP.

## Login Rules
1. Student uses student account credentials.
2. Faculty uses pre-seeded account credentials.
3. Inactive users cannot authenticate.

## Session Rules
1. Access token required for protected endpoints.
2. Refresh token can renew access token until refresh expiry.
3. Invalid/expired tokens must return `401`.

## Security Rules
1. Passwords are hashed before storage.
2. Secrets and JWT config come from environment variables.
3. API responses must not return password hashes or sensitive internals.
