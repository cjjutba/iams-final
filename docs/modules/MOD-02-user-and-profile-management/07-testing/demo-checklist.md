# Demo Checklist (MOD-02)

- [ ] Admin can list users with pagination (includes phone, email_confirmed in response).
- [ ] Admin can fetch a specific user by ID (full profile fields).
- [ ] Student profile view returns correct data including phone and email_confirmed.
- [ ] Faculty profile view returns correct data including phone and email_confirmed.
- [ ] Student can update first_name, last_name, and phone successfully.
- [ ] Faculty can update first_name, last_name, and phone successfully.
- [ ] Email field is displayed as read-only on edit screens.
- [ ] Attempting to change email via API returns `400`.
- [ ] Restricted field update (role, student_id) is blocked for non-admin.
- [ ] Admin can update restricted fields (role, is_active).
- [ ] Admin can permanently delete a user.
- [ ] Deleted user is removed from local DB.
- [ ] Deleted user is removed from Supabase Auth.
- [ ] Deleted user's face registrations are cleaned up.
- [ ] Unauthorized role access to admin endpoints is blocked.
- [ ] All endpoints require valid Supabase JWT.
