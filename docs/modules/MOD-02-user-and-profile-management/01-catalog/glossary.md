# Glossary

- **User Directory:** Admin-scoped list of user records.
- **Profile Update:** Controlled modification of editable user fields (first_name, last_name, phone).
- **Immutable Field:** A field that cannot be changed after initial creation (e.g., email).
- **Hard Delete:** Permanent row removal from local DB and Supabase Auth, with cascade cleanup of related records.
- **Field-Level Authorization:** Restricting which fields a role can update (students/faculty can edit name and phone; only admin can change role or is_active).
- **Cascade Impact:** Effects on related tables (e.g., `face_registrations`, FAISS index) when a user is deleted.
- **Supabase Auth User:** The authentication record managed by Supabase Auth; must be deleted when the local user record is deleted.
- **Supabase Admin API:** Server-side Supabase API used to manage users (e.g., `supabase.auth.admin.deleteUser()`).
- **Supabase JWT:** JSON Web Token issued by Supabase Auth; verified by backend middleware on all MOD-02 endpoints.
