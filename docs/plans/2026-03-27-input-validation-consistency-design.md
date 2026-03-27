# Input Validation & Consistency Design

**Date:** 2026-03-27
**Status:** Approved

## Problem

24 input fields across 10 screens in the Android app have inconsistent validation, error display, and sanitization:

- Auth screens use Toast-only errors; profile screens use inline errors
- Registration requires 6-char passwords; everywhere else requires 8
- FacultyManualEntryScreen uses raw `BasicTextField` instead of `IAMSTextField`
- Email validation ranges from `contains("@")` to `Patterns.EMAIL_ADDRESS`
- Sanitization (trim, case conversion) is ad-hoc per screen
- ResetPasswordScreen has no client-side validation at all
- Birthdate accepts invalid dates like `99991399`

## Approach

**Centralized Validation Utility (Approach A)** — Create `InputValidation.kt` with reusable pure validation functions. Migrate all screens to hybrid error pattern: inline errors for field-specific validation, Toast/snackbar for network and backend errors.

## Design

### 1. InputValidation.kt

New file: `android/app/src/main/java/com/iams/app/ui/utils/InputValidation.kt`

```kotlin
object InputValidation {
    fun validateEmail(email: String): String?          // Patterns.EMAIL_ADDRESS
    fun validatePassword(password: String, minLength: Int = 8): String?
    fun validatePasswordMatch(password: String, confirm: String): String?
    fun validateRequired(value: String, fieldName: String): String?
    fun validatePhone(phone: String): String?          // ^09\d{9}$
    fun validateStudentId(studentId: String): String?  // non-blank
    fun validateBirthdate(mmddyyyy: String): String?   // month 01-12, day 01-31, year 1950-2015
}

object InputSanitizer {
    fun email(value: String): String        // trim + lowercase
    fun studentId(value: String): String    // trim + uppercase
    fun trimmed(value: String): String      // just trim
    fun digitsOnly(value: String, maxLength: Int): String  // filter digits + take(maxLength)
}
```

Returns `null` if valid, error message `String` if invalid.

### 2. IAMSTextField Enhancement

Two new optional parameters:

- `maxLength: Int? = null` — Truncates input in onValueChange; optionally shows counter
- `supportingText: String? = null` — Helper text below field (e.g., "Format: MMDDYYYY"), shown in TextTertiary when no error present

No other changes. The component is already well-built.

### 3. Error Display Pattern (Hybrid)

| Error Type | Display Method |
|-----------|---------------|
| Field validation (empty, format, match) | Inline below field via `error` param on `IAMSTextField` |
| Backend validation (401, 403, 404) | Toast/snackbar |
| Network errors | Toast/snackbar |
| Success messages | Toast/snackbar |

### 4. Screen-by-Screen Changes

#### Auth Screens → Inline errors + Toast for network/backend

**StudentLoginScreen & FacultyLoginScreen:**
- Add local error state per field
- Validate with `InputValidation` on submit, show inline errors
- Backend/network errors remain as Toast
- Apply `InputSanitizer` before API call

**RegisterStep1Screen:**
- Add inline error for student ID via `validateRequired()`
- Add inline error for birthdate via `validateBirthdate()` (not just length check)
- Backend errors remain as Toast

**RegisterStep2Screen:**
- Replace all Toast validations with inline field errors
- Standardize password minimum from 6 → 8 characters
- Apply `InputSanitizer.email()` before storing in `RegistrationDataHolder`

**ForgotPasswordScreen:**
- Add inline email validation via `validateEmail()`
- Network/backend errors remain as Toast

**ResetPasswordScreen:**
- Add local error state for password and confirm fields
- Validate password length and match with inline errors
- Network errors remain as Toast

#### Profile Screens → Minor refactor

**StudentEditProfileViewModel & FacultyEditProfileViewModel:**
- Replace inline validation logic with `InputValidation` calls
- Add `InputSanitizer` calls before API requests
- No structural changes — already uses inline errors correctly

#### Faculty Manual Entry → Visual consistency

**FacultyManualEntryScreen:**
- Replace raw `BasicTextField` (Student ID) with `IAMSTextField`
- Replace raw `BasicTextField` (Remarks) with `IAMSTextField` (singleLine=false)
- Add `InputSanitizer.studentId()` and `InputSanitizer.trimmed()` before submit
- Keep AlertDialog for submit success/error (appropriate for this screen)

### 5. Password Minimum Length Standardization

| Location | Current | New |
|----------|---------|-----|
| RegisterStep2Screen | 6 chars | 8 chars |
| ResetPasswordViewModel | 8 chars | 8 chars |
| StudentEditProfileViewModel | 8 chars | 8 chars |
| FacultyEditProfileViewModel | 8 chars | 8 chars |

All go through `InputValidation.validatePassword(minLength = 8)`.

### 6. Scope Boundaries (NOT changing)

- No password strength indicator
- No real-time keystroke validation on auth screens
- No changes to backend validation
- No changes to Toast/Snackbar component
- No new dependencies
- Profile ViewModel structure stays the same

## Files Affected

| File | Change Type |
|------|------------|
| `ui/utils/InputValidation.kt` | **New** |
| `ui/components/IAMSTextField.kt` | Enhanced (maxLength, supportingText) |
| `ui/auth/StudentLoginScreen.kt` | Inline errors |
| `ui/auth/FacultyLoginScreen.kt` | Inline errors |
| `ui/auth/RegisterStep1Screen.kt` | Inline errors + birthdate validation |
| `ui/auth/RegisterStep2Screen.kt` | Inline errors + password 6→8 |
| `ui/auth/ForgotPasswordScreen.kt` | Inline email error |
| `ui/auth/ResetPasswordScreen.kt` | Inline password errors |
| `ui/auth/LoginViewModel.kt` | Sanitization |
| `ui/auth/ResetPasswordViewModel.kt` | Use InputValidation |
| `ui/student/StudentEditProfileViewModel.kt` | Use InputValidation + InputSanitizer |
| `ui/faculty/FacultyEditProfileViewModel.kt` | Use InputValidation + InputSanitizer |
| `ui/faculty/FacultyManualEntryScreen.kt` | Switch to IAMSTextField |
| `ui/faculty/FacultyManualEntryViewModel.kt` | Use InputValidation + InputSanitizer |

## Lessons

- Registration used 6-char min password while all other screens used 8 — easy to miss when validation is scattered across files.
- Raw `BasicTextField` in one screen while every other screen uses the shared component creates visual drift that's hard to catch in review.
- Toast-only errors on auth screens make it impossible for users to know which field has the problem.
