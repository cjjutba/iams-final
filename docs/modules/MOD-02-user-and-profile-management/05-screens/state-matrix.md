# Screen State Matrix

## Common States
| Screen | Loading | Success | Validation Error | Network Error |
|---|---|---|---|---|
| SCR-015 StudentProfileScreen | Skeleton/loading card | Render profile (name, email, student_id, phone, email_confirmed) | N/A | Retry + message |
| SCR-016 StudentEditProfileScreen | Disable save + spinner | Show saved confirmation | Inline field errors (email immutable error) | Retry + preserve input |
| SCR-027 FacultyProfileScreen | Skeleton/loading card | Render profile (name, email, phone, email_confirmed) | N/A | Retry + message |
| SCR-028 FacultyEditProfileScreen | Disable save + spinner | Show saved confirmation | Inline field errors (email immutable error) | Retry + preserve input |

## Required UX Rules
- Preserve user-edited values on recoverable errors.
- Show clear feedback on successful update.
- Do not expose restricted fields in editable form (email shown as read-only, role/student_id/is_active hidden from non-admin).
- Phone field should be editable with appropriate input type (phone keyboard).
- Email field must be displayed but clearly marked as non-editable.
