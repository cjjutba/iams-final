# Integration Points

## Backend Integrations
- User repository / database access layer
- Password hashing and JWT utility functions
- Request validation and exception handling middleware

## Mobile Integrations
- Auth screens state management
- Secure token storage/session restore
- API service layer for `/auth/*` endpoints

## Data Integrations
- University identity source produced by import scripts
- Faculty account pre-seeding workflow

## Downstream Module Consumers
- `MOD-09` Student app session flow
- `MOD-10` Faculty app session flow
- Protected endpoints across other backend modules
