# Implementation Plan (MOD-02)

## Phase 1: Foundations
- Confirm Supabase JWT middleware and role checks from `MOD-01` are working.
- Confirm user repository, schemas, and Supabase Admin API client are in place.
- Verify `users` table has all required columns (phone, email_confirmed_at, no password_hash).

## Phase 2: Profile Core
- Implement `FUN-02-02` get user by ID (include phone, student_id, email_confirmed, created_at in response).
- Implement `FUN-02-03` update profile fields with field rules:
  - Editable: first_name, last_name, phone.
  - Immutable: email (reject with `400` for all roles).
  - Admin-only: role, student_id, is_active.

## Phase 3: Admin Operations
- Implement `FUN-02-01` list users with pagination/filter (include phone, email_confirmed in list items).
- Implement `FUN-02-04` permanent delete with full cleanup:
  1. Delete face_registrations.
  2. FAISS index cleanup.
  3. Delete Supabase Auth user via Admin API.
  4. Delete local users row.
  5. Rollback on Supabase Auth failure.

## Phase 4: Mobile Integration
- Connect profile screens to get/update endpoints with Supabase JWT.
- Display phone field in profile views and edit forms.
- Display email as read-only in edit forms.
- Handle field validation and error states.

## Phase 5: Validation
- Run unit/integration/E2E tests.
- Validate acceptance criteria and update traceability.
- Verify delete cleans up both local DB and Supabase Auth.
