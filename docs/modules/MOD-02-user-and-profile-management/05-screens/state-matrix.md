# Screen State Matrix

## Common States
| Screen | Loading | Success | Validation Error | Network Error |
|---|---|---|---|---|
| SCR-015 StudentProfileScreen | Skeleton/loading card | Render profile data | N/A | Retry + message |
| SCR-016 StudentEditProfileScreen | Disable save + spinner | Show saved confirmation | Inline field errors | Retry + preserve input |
| SCR-027 FacultyProfileScreen | Skeleton/loading card | Render profile data | N/A | Retry + message |
| SCR-028 FacultyEditProfileScreen | Disable save + spinner | Show saved confirmation | Inline field errors | Retry + preserve input |

## Required UX Rules
- Preserve user-edited values on recoverable errors.
- Show clear feedback on successful update.
- Do not expose restricted fields in editable form.
