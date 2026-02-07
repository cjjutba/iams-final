# Data Model Inventory

## Primary Data Stores Used by MOD-02
1. `users` table (profile and identity fields)
2. `face_registrations` table (lifecycle linkage to user state)

## Entities
- User profile record
- User role and account state (`is_active`)
- Face registration linkage for lifecycle handling

## Ownership
- `users`: backend data layer
- `face_registrations`: face module data, referenced for lifecycle impact
