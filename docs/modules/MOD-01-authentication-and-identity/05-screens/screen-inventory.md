# Screen Inventory (MOD-01)

## Included Screens
| Screen ID | Screen Name | Role | Auth Module Usage |
|---|---|---|---|
| SCR-004 | StudentLoginScreen | Student | Login entry point |
| SCR-005 | FacultyLoginScreen | Faculty | Login entry point (pre-seeded only) |
| SCR-006 | ForgotPasswordScreen | Student/Faculty | Password reset initiation flow |
| SCR-007 | StudentRegisterStep1Screen | Student | Identity verification (`FUN-01-01`) |
| SCR-008 | StudentRegisterStep2Screen | Student | Account setup payload preparation |
| SCR-010 | StudentRegisterReviewScreen | Student | Registration submit (`FUN-01-02`) |

## Cross-Screen Dependencies
- Registration Step 3 (`SCR-009`) is part of face module (`MOD-03`) but depends on successful auth registration sequencing.
- Session restore after login routes to role-specific home screens.
