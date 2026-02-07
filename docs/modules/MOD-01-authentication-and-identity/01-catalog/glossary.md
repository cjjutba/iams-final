# Glossary

- Access Token: Short-lived bearer JWT used on protected API requests.
- Refresh Token: Longer-lived token used to request a new access token.
- Identity Verification: Pre-registration check that student ID exists in university dataset.
- Pre-seeded Faculty: Faculty account created ahead of time by import/seed process.
- Protected Route: Endpoint requiring `Authorization: Bearer <token>`.
- JWT: JSON Web Token used for stateless auth claims.
- Auth Context: Current authenticated user identity and role resolved from token.
