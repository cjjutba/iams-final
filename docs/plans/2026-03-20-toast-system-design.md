# Toast System Design — Comprehensive Integration

**Date:** 2026-03-20
**Status:** Approved

## Overview

Wire the existing `IAMSToast` component into all screens that have user-facing actions (login, registration, password reset, data loading, profile edits). The toast infrastructure (`ToastState`, `LocalToastState`, `IAMSToastHost`) already exists and is provided at the root `IAMSNavHost` level. The work is purely integration — adding `toastEvent` flows to ViewModels and `LaunchedEffect` observers in screens.

## Approach

**ViewModel-driven toasts via `SharedFlow<ToastData>`** — Each ViewModel that triggers user-facing events emits toast data through a `SharedFlow`. Screens collect the flow in a `LaunchedEffect` and call `toastState.showToast()`. This keeps toast logic in ViewModels (testable) and rendering in Compose (reactive).

For auth screens, inline field errors are **replaced** by toasts to avoid duplication.

## Toast Triggers

### Auth — Login
| Screen | Event | Type | Message |
|--------|-------|------|---------|
| StudentLoginScreen | Login success | SUCCESS | "Welcome back!" |
| StudentLoginScreen | Wrong credentials | ERROR | "Invalid credentials" |
| StudentLoginScreen | Network error | ERROR | "Network error. Check your connection." |
| FacultyLoginScreen | Login success | SUCCESS | "Welcome back!" |
| FacultyLoginScreen | Wrong credentials | ERROR | "Invalid credentials" |
| FacultyLoginScreen | Network error | ERROR | "Network error. Check your connection." |

### Auth — Registration
| Screen | Event | Type | Message |
|--------|-------|------|---------|
| RegisterStep1 | Student verified | SUCCESS | "Student ID verified" |
| RegisterStep1 | ID not found / already registered | ERROR | (API error message) |
| RegisterStep2 | Account created | SUCCESS | "Account created! Check your email." |
| RegisterStep2 | Email exists / validation error | ERROR | (API error message) |
| EmailVerification | Resend success | SUCCESS | "Verification email sent!" |
| EmailVerification | Email verified | SUCCESS | "Email verified!" |
| EmailVerification | Error | ERROR | (error message) |
| RegisterStep3 | Face captured | INFO | "Photo {n} captured" |
| RegisterReview | Upload success | SUCCESS | "Face registration complete!" |
| RegisterReview | Upload failed | ERROR | (error message) |

### Auth — Password
| Screen | Event | Type | Message |
|--------|-------|------|---------|
| ForgotPassword | Reset link sent | SUCCESS | "Reset link sent to your email" |
| ForgotPassword | Error | ERROR | (error message) |
| ResetPassword | Password reset | SUCCESS | "Password reset successfully" |
| ResetPassword | Error | ERROR | (error message) |

### Data Screens
| Screen | Event | Type | Message |
|--------|-------|------|---------|
| FacultyReports | Report error | ERROR | (error from generateReport) |
| StudentHome | Load error | ERROR | (error message) |
| StudentHistory | Load error | ERROR | (error message) |
| StudentSchedule | Load error | ERROR | (error message) |
| FacultyProfile | Load error | ERROR | (error message) |
| StudentProfile | Load error | ERROR | (error message) |

### Already Wired (no changes needed)
- FacultyHomeScreen — session messages
- FacultyEditProfileScreen — profile/password success/error
- StudentEditProfileScreen — profile/password success/error
- FacultyReportsScreen — "Coming soon" toasts (partial, needs error wiring)

## Files Changed

### ViewModels
- `LoginViewModel.kt` — Add `toastEvent: SharedFlow<ToastData>`, emit on success/error
- `RegistrationViewModel.kt` — Add `toastEvent: SharedFlow<ToastData>`, emit on all step outcomes
- `ForgotPasswordViewModel.kt` — Add `toastEvent: SharedFlow<ToastData>`
- `ResetPasswordViewModel.kt` — Add `toastEvent: SharedFlow<ToastData>`

### Screens
- `StudentLoginScreen.kt` — Add LaunchedEffect for toastEvent, remove inline error from TextField
- `FacultyLoginScreen.kt` — Add LaunchedEffect for toastEvent, remove inline error from TextField
- `RegisterStep1Screen.kt` — Add LaunchedEffect for toastEvent, remove inline error
- `RegisterStep2Screen.kt` — Add LaunchedEffect for toastEvent, remove inline error
- `RegisterStep3Screen.kt` — Add toast on face capture
- `EmailVerificationScreen.kt` — Add LaunchedEffect for toastEvent
- `RegisterReviewScreen.kt` — Add LaunchedEffect for toastEvent, remove inline error Text
- `ForgotPasswordScreen.kt` — Add LaunchedEffect for toastEvent, remove inline error
- `ResetPasswordScreen.kt` — Add LaunchedEffect for toastEvent, remove inline error
- `FacultyReportsScreen.kt` — Wire uiState.error to toast
- `StudentHomeScreen.kt` — Wire uiState.error to toast
- `StudentHistoryScreen.kt` — Wire uiState.error to toast
- `StudentScheduleScreen.kt` — Wire uiState.error to toast
- `FacultyProfileScreen.kt` — Wire uiState.error to toast
- `StudentProfileScreen.kt` — Wire uiState.error to toast
