# Glossary

- User Directory: Admin-scoped list of user records.
- Profile Update: Controlled modification of editable user fields.
- Soft Delete/Deactivate: Setting `is_active=false` instead of permanent row deletion.
- Hard Delete: Permanent row removal (requires strict safeguards).
- Field-Level Authorization: Restricting which fields a role can update.
- Cascade Impact: Effects on related tables (for example `face_registrations`) when a user is deleted/deactivated.
