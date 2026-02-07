# Screen State Matrix

## Common States
| Screen | Loading | Success | Validation Error | Network Error |
|---|---|---|---|---|
| SCR-004 StudentLoginScreen | Disable submit + spinner | Route to home | Inline field error | Retry + message |
| SCR-005 FacultyLoginScreen | Disable submit + spinner | Route to home | Invalid creds message | Retry + message |
| SCR-006 ForgotPasswordScreen | Disable submit + spinner | Confirmation notice | Invalid email format | Retry + message |
| SCR-007 Step1 Verify ID | Disable verify button | Show identity card | Invalid student ID input | Retry + message |
| SCR-008 Step2 Account Setup | Disable continue button | Go to review screen | Field-level errors | Retry + message |
| SCR-010 Review Submit | Disable submit + spinner | Registration success | Duplicate email/student ID | Retry + message |

## Required UX Rules
- Never leave form in ambiguous state after API failure.
- Preserve user-entered data on recoverable errors.
- Always provide actionable next step on failure.
