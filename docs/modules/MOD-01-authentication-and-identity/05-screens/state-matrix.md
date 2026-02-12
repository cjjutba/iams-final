# Screen State Matrix

## Common States
| Screen | Loading | Success | Validation Error | Network Error |
|---|---|---|---|---|
| SCR-004 StudentLoginScreen | Disable submit + spinner | Route to home (via `GET /auth/me`) | Inline field error / Supabase error message | Retry + message |
| SCR-005 FacultyLoginScreen | Disable submit + spinner | Route to home (via `GET /auth/me`) | Invalid creds message (Supabase error) | Retry + message |
| SCR-006 ForgotPasswordScreen | Disable submit + spinner | "Check your email" confirmation | Invalid email format | Retry + message |
| SCR-007 Step1 Verify ID | Disable verify button | Show identity card | Invalid student ID input | Retry + message |
| SCR-008 Step2 Account Setup | Disable continue button | Go to review screen | Field-level errors (email, phone, password) | Retry + message |
| SCR-010 Review Submit | Disable submit + spinner | Navigate to EmailVerificationPendingScreen | Duplicate email/student ID (409) | Retry + message |
| SCR-NEW EmailVerificationPending | N/A | "Go to Login" button | N/A | Retry "Resend Email" |
| SCR-NEW SetNewPasswordScreen | Disable submit + spinner | "Password updated" + navigate to login | Weak password error | Retry + message |

## Auth-Specific States
| Screen | Email Not Confirmed | Account Inactive |
|---|---|---|
| SCR-004 StudentLoginScreen | Show "Please verify your email first" (from Supabase or `GET /auth/me` 403) | Show "Account deactivated" (from `GET /auth/me` 403) |
| SCR-005 FacultyLoginScreen | Show "Please verify your email first" | Show "Account deactivated" |

## Required UX Rules
- Never leave form in ambiguous state after API failure.
- Preserve user-entered data on recoverable errors.
- Always provide actionable next step on failure.
- On email not confirmed: show link to resend verification email.
- On account inactive: show "Contact your administrator."
