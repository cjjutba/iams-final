# Screen State Matrix

## Common States
| Screen | Loading | Success | Validation Error | Network Error | Auth Error |
|---|---|---|---|---|---|
| SCR-009 Register Step 3 | Disable submit + spinner | Show registration success | show image issue reason | retry + preserve captured set | redirect to login (expired JWT) |
| SCR-017 Face Re-register | Disable submit + spinner | show updated registration status | show validation reason | retry + preserve captured set | redirect to login (expired JWT) |
| SCR-030 Camera | capture processing indicator | image captured | image rejected prompt | camera/access retry prompt | n/a |

## Required UX Rules
- Display explicit reason when image is rejected.
- Keep captured images until user retries or resets.
- Prevent submit until minimum valid image count is met (3).
- If Supabase JWT is expired or invalid, prompt user to re-login.
- Show `403` error clearly if user account is inactive or email not confirmed.
