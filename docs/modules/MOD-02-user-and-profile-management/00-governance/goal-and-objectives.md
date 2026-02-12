# Goal and Objectives

## Module Goal
Provide reliable, role-aware user data retrieval and profile management, with safe update and permanent delete behavior, coordinated with Supabase Auth for user lifecycle operations.

## Primary Objectives
1. Provide admin-scoped user listing and retrieval endpoints.
2. Provide user record retrieval by ID with authorization controls.
3. Support profile updates with validation and field restrictions (first_name, last_name, phone editable; email immutable).
4. Support permanent delete operations with full cleanup (local DB + Supabase Auth user + face registrations + FAISS index).

## Success Outcomes
- User endpoints return consistent, validated payloads including phone and email_confirmed status.
- Role-based access is enforced on all user routes via Supabase JWT middleware.
- Profile updates persist correctly and preserve data integrity.
- Delete behavior permanently removes user from both local DB and Supabase Auth, with cascade cleanup of related records.

## Non-Goals (for MOD-02 MVP)
- Full admin dashboard UI implementation.
- Bulk user import logic (owned by data import module).
- Complex permission management interface.
- Rate limiting on user endpoints.

## Stakeholders
- Students and faculty: view/edit their profile data (name, phone).
- Admin/operations: list, inspect, and delete user records.
- Backend/mobile implementers: integrate profile APIs and screens.
