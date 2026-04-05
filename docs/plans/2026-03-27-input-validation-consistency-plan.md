# Input Validation Consistency Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Standardize all 24 input fields across 10 screens with centralized validation, consistent inline error display, and proper sanitization.

**Architecture:** Create `InputValidation.kt` utility with pure validation/sanitization functions. Migrate auth screens from Toast-only to hybrid (inline + toast) error pattern. Replace raw `BasicTextField` usage with `IAMSTextField`.

**Tech Stack:** Kotlin, Jetpack Compose, `android.util.Patterns`

**Design doc:** `docs/plans/2026-03-27-input-validation-consistency-design.md`

---

### Task 1: Create InputValidation.kt utility

**Files:**
- Create: `android/app/src/main/java/com/iams/app/ui/utils/InputValidation.kt`

**Step 1: Create the validation and sanitization utility**

```kotlin
package com.iams.app.ui.utils

import android.util.Patterns

/**
 * Centralized input validation. Returns null if valid, error message if invalid.
 */
object InputValidation {

    fun validateRequired(value: String, fieldName: String): String? {
        return if (value.isBlank()) "$fieldName is required" else null
    }

    fun validateEmail(email: String): String? {
        if (email.isBlank()) return "Email is required"
        if (!Patterns.EMAIL_ADDRESS.matcher(email).matches()) return "Invalid email address"
        return null
    }

    fun validatePassword(password: String, minLength: Int = 8): String? {
        if (password.isBlank()) return "Password is required"
        if (password.length < minLength) return "Password must be at least $minLength characters"
        return null
    }

    fun validatePasswordMatch(password: String, confirmPassword: String): String? {
        if (confirmPassword.isBlank()) return "Please confirm your password"
        if (password != confirmPassword) return "Passwords do not match"
        return null
    }

    fun validatePhone(phone: String): String? {
        if (phone.isBlank()) return "Phone number is required"
        if (!phone.matches(Regex("^09\\d{9}$"))) return "Invalid phone number (09XXXXXXXXX)"
        return null
    }

    fun validatePhoneOptional(phone: String): String? {
        if (phone.isBlank()) return null
        if (!phone.matches(Regex("^09\\d{9}$"))) return "Invalid phone number (09XXXXXXXXX)"
        return null
    }

    fun validateStudentId(studentId: String): String? {
        return if (studentId.isBlank()) "Student ID is required" else null
    }

    fun validateBirthdate(mmddyyyy: String): String? {
        if (mmddyyyy.length != 8) return "Enter birthdate as MMDDYYYY"
        val mm = mmddyyyy.substring(0, 2).toIntOrNull() ?: return "Invalid month"
        val dd = mmddyyyy.substring(2, 4).toIntOrNull() ?: return "Invalid day"
        val yyyy = mmddyyyy.substring(4, 8).toIntOrNull() ?: return "Invalid year"
        if (mm !in 1..12) return "Month must be 01-12"
        if (dd !in 1..31) return "Day must be 01-31"
        if (yyyy !in 1950..2015) return "Year must be 1950-2015"
        return null
    }
}

/**
 * Centralized input sanitization applied before API calls.
 */
object InputSanitizer {
    fun email(value: String): String = value.trim().lowercase()
    fun studentId(value: String): String = value.trim().uppercase()
    fun trimmed(value: String): String = value.trim()
    fun digitsOnly(value: String, maxLength: Int): String = value.filter { it.isDigit() }.take(maxLength)
}
```

**Step 2: Verify it compiles**

Run: `cd android && ./gradlew compileDebugKotlin 2>&1 | tail -5`
Expected: BUILD SUCCESSFUL

**Step 3: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/utils/InputValidation.kt
git commit -m "feat(android): add centralized InputValidation and InputSanitizer utilities"
```

---

### Task 2: Enhance IAMSTextField with maxLength and supportingText

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/components/IAMSTextField.kt`

**Step 1: Add new parameters and logic**

Add to the function signature (after `trailingIcon`):
```kotlin
    maxLength: Int? = null,
    supportingText: String? = null,
```

Wrap the existing `onValueChange` to enforce maxLength — change the `BasicTextField`'s `onValueChange`:
```kotlin
onValueChange = { newValue ->
    if (maxLength != null) {
        if (newValue.length <= maxLength) onValueChange(newValue)
    } else {
        onValueChange(newValue)
    }
},
```

After the existing error display block (after the closing `}` of `if (error != null)`), add supporting text:
```kotlin
        // Supporting text (shown when no error)
        if (error == null && supportingText != null) {
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = supportingText,
                style = MaterialTheme.typography.bodySmall,
                color = TextTertiary,
            )
        }
```

**Step 2: Verify it compiles**

Run: `cd android && ./gradlew compileDebugKotlin 2>&1 | tail -5`
Expected: BUILD SUCCESSFUL (existing callers unaffected — both params have defaults)

**Step 3: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/components/IAMSTextField.kt
git commit -m "feat(android): add maxLength and supportingText to IAMSTextField"
```

---

### Task 3: StudentLoginScreen — inline validation errors

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/StudentLoginScreen.kt`

**Step 1: Add imports and local error state**

Add import:
```kotlin
import com.iams.app.ui.utils.InputValidation
import com.iams.app.ui.utils.InputSanitizer
```

After `var password by remember { mutableStateOf("") }`, add:
```kotlin
    var studentIdError by remember { mutableStateOf<String?>(null) }
    var passwordError by remember { mutableStateOf<String?>(null) }
```

**Step 2: Add validation function**

Add a local `submit()` function before the `AuthLayout` call:
```kotlin
    fun submit() {
        val idErr = InputValidation.validateStudentId(studentId)
        val pwErr = InputValidation.validateRequired(password, "Password")
        studentIdError = idErr
        passwordError = pwErr
        if (idErr != null || pwErr != null) return
        focusManager.clearFocus()
        viewModel.login(InputSanitizer.studentId(studentId), InputSanitizer.trimmed(password))
    }
```

**Step 3: Wire error state to fields**

On the Student ID `IAMSTextField`, add `error = studentIdError` and change `onValueChange`:
```kotlin
            onValueChange = {
                studentId = it
                studentIdError = null
                viewModel.clearError()
            },
            // ... existing props ...
            error = studentIdError,
```

On the Password `IAMSTextField`, change `error = null` to `error = passwordError` and change `onValueChange`:
```kotlin
            onValueChange = {
                password = it
                passwordError = null
                viewModel.clearError()
            },
            // ... existing props ...
            error = passwordError,
```

**Step 4: Replace inline login calls with submit()**

Change the `onDone` keyboard action (line ~131):
```kotlin
            keyboardActions = KeyboardActions(
                onDone = { submit() }
            )
```

Change the Login button `onClick` (line ~158):
```kotlin
            onClick = { submit() },
```

Remove the old `viewModel.login(studentId.trim().uppercase(), password.trim())` calls — they're now in `submit()`.

**Step 5: Verify it compiles**

Run: `cd android && ./gradlew compileDebugKotlin 2>&1 | tail -5`
Expected: BUILD SUCCESSFUL

**Step 6: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/StudentLoginScreen.kt
git commit -m "feat(android): add inline validation errors to StudentLoginScreen"
```

---

### Task 4: FacultyLoginScreen — inline validation errors

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/FacultyLoginScreen.kt`

**Step 1: Same pattern as Task 3**

Add imports:
```kotlin
import com.iams.app.ui.utils.InputValidation
import com.iams.app.ui.utils.InputSanitizer
```

After `var password by remember { mutableStateOf("") }`, add:
```kotlin
    var emailError by remember { mutableStateOf<String?>(null) }
    var passwordError by remember { mutableStateOf<String?>(null) }
```

Add submit function:
```kotlin
    fun submit() {
        val eErr = InputValidation.validateEmail(email)
        val pErr = InputValidation.validateRequired(password, "Password")
        emailError = eErr
        passwordError = pErr
        if (eErr != null || pErr != null) return
        focusManager.clearFocus()
        viewModel.login(InputSanitizer.email(email), InputSanitizer.trimmed(password))
    }
```

**Step 2: Wire error state to fields**

Email field — add `error = emailError`, update `onValueChange` to also clear `emailError`:
```kotlin
            onValueChange = {
                email = it
                emailError = null
                viewModel.clearError()
            },
            error = emailError,
```

Password field — change `error = null` to `error = passwordError`, update `onValueChange`:
```kotlin
            onValueChange = {
                password = it
                passwordError = null
                viewModel.clearError()
            },
            error = passwordError,
```

**Step 3: Replace login calls with submit()**

`onDone`: `onDone = { submit() }`
Button `onClick`: `onClick = { submit() }`

**Step 4: Verify and commit**

Run: `cd android && ./gradlew compileDebugKotlin 2>&1 | tail -5`

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/FacultyLoginScreen.kt
git commit -m "feat(android): add inline validation errors to FacultyLoginScreen"
```

---

### Task 5: RegisterStep1Screen — inline errors + birthdate validation

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/RegisterStep1Screen.kt`

**Step 1: Add imports and error state**

```kotlin
import com.iams.app.ui.utils.InputValidation
import com.iams.app.ui.utils.InputSanitizer
```

After `var birthdate by remember { mutableStateOf("") }`, add:
```kotlin
    var studentIdError by remember { mutableStateOf<String?>(null) }
    var birthdateError by remember { mutableStateOf<String?>(null) }
```

**Step 2: Wire error state to Student ID field**

```kotlin
            onValueChange = {
                studentId = it
                studentIdError = null
                viewModel.clearError()
            },
            error = studentIdError,
```

**Step 3: Wire error state to Birthdate field**

Change the existing `onValueChange` to also use `InputSanitizer.digitsOnly`:
```kotlin
                onValueChange = { newValue ->
                    birthdate = InputSanitizer.digitsOnly(newValue, 8)
                    birthdateError = null
                    viewModel.clearError()
                },
                error = birthdateError,
                supportingText = "Format: MMDDYYYY",
```

**Step 4: Add validation to submit actions**

For the Phase 1 Continue button, add validation before `viewModel.checkStudentId`:
```kotlin
            IAMSButton(
                text = "Continue",
                onClick = {
                    val err = InputValidation.validateStudentId(studentId)
                    studentIdError = err
                    if (err != null) return@IAMSButton
                    viewModel.checkStudentId(studentId)
                },
                enabled = !uiState.isLoading && studentId.isNotBlank(),
                isLoading = uiState.isLoading,
                loadingText = "Checking..."
            )
```

For the Phase 2 Verify button, replace the length check with proper validation:
```kotlin
            IAMSButton(
                text = "Verify",
                onClick = {
                    val err = InputValidation.validateBirthdate(birthdate)
                    birthdateError = err
                    if (err != null) return@IAMSButton
                    val formatted = formatBirthdateForApi(birthdate)
                    viewModel.verifyStudentId(studentId, formatted)
                },
                enabled = !uiState.isLoading && birthdate.length == 8,
                isLoading = uiState.isLoading,
                loadingText = "Verifying..."
            )
```

Also update the `onDone` keyboard action for birthdate:
```kotlin
                keyboardActions = KeyboardActions(
                    onDone = {
                        focusManager.clearFocus()
                        val err = InputValidation.validateBirthdate(birthdate)
                        birthdateError = err
                        if (err != null) return@KeyboardActions
                        val formatted = formatBirthdateForApi(birthdate)
                        viewModel.verifyStudentId(studentId, formatted)
                    }
                )
```

Remove the Toast-based birthdate error in the old Verify button onClick (the `toastState.showToast("Please enter a valid birthdate...")` call).

**Step 5: Verify and commit**

Run: `cd android && ./gradlew compileDebugKotlin 2>&1 | tail -5`

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/RegisterStep1Screen.kt
git commit -m "feat(android): add inline validation + birthdate validation to RegisterStep1Screen"
```

---

### Task 6: RegisterStep2Screen — inline errors + password standardization

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/RegisterStep2Screen.kt`

**Step 1: Add imports and error state**

```kotlin
import com.iams.app.ui.utils.InputValidation
import com.iams.app.ui.utils.InputSanitizer
```

After `var confirmPassword by remember { mutableStateOf("") }`, add:
```kotlin
    var emailError by remember { mutableStateOf<String?>(null) }
    var passwordError by remember { mutableStateOf<String?>(null) }
    var confirmPasswordError by remember { mutableStateOf<String?>(null) }
```

**Step 2: Rewrite proceed() to use InputValidation with inline errors**

Replace the entire `proceed()` function:
```kotlin
    fun proceed() {
        val eErr = InputValidation.validateEmail(email)
        val pErr = InputValidation.validatePassword(password, minLength = 8)
        val cErr = InputValidation.validatePasswordMatch(password, confirmPassword)
        emailError = eErr
        passwordError = pErr
        confirmPasswordError = cErr
        if (eErr != null || pErr != null || cErr != null) return

        // Store data for Step 4 (Review) — no API call yet
        RegistrationDataHolder.studentId = studentId
        RegistrationDataHolder.firstName = firstName
        RegistrationDataHolder.lastName = lastName
        RegistrationDataHolder.email = InputSanitizer.email(email)
        RegistrationDataHolder.password = password

        // Navigate to face capture (Step 3)
        navController.navigate(Routes.REGISTER_FACE_FLOW)
    }
```

**Step 3: Wire error state to fields**

Email field:
```kotlin
        IAMSTextField(
            value = email,
            onValueChange = {
                email = it
                emailError = null
            },
            label = "Email",
            placeholder = "your.email@example.com",
            error = emailError,
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Email,
                imeAction = ImeAction.Next
            ),
            keyboardActions = KeyboardActions(
                onNext = { focusManager.moveFocus(FocusDirection.Down) }
            )
        )
```

Password field:
```kotlin
        IAMSTextField(
            value = password,
            onValueChange = {
                password = it
                passwordError = null
            },
            label = "Password",
            placeholder = "At least 8 characters",
            isPassword = true,
            error = passwordError,
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Next
            ),
            keyboardActions = KeyboardActions(
                onNext = { focusManager.moveFocus(FocusDirection.Down) }
            )
        )
```

Confirm Password field:
```kotlin
        IAMSTextField(
            value = confirmPassword,
            onValueChange = {
                confirmPassword = it
                confirmPasswordError = null
            },
            label = "Confirm Password",
            placeholder = "Re-enter your password",
            isPassword = true,
            error = confirmPasswordError,
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Done
            ),
            keyboardActions = KeyboardActions(
                onDone = {
                    focusManager.clearFocus()
                    proceed()
                }
            )
        )
```

**Step 4: Remove unused Toast import if no longer needed**

Check if `LocalToastState` and `ToastType` are still used. Since `proceed()` no longer uses Toasts, but the screen may still need them for future backend errors — keep imports for now but remove Toast calls from `proceed()`.

**Step 5: Verify and commit**

Run: `cd android && ./gradlew compileDebugKotlin 2>&1 | tail -5`

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/RegisterStep2Screen.kt
git commit -m "feat(android): inline validation errors + 8-char password in RegisterStep2Screen"
```

---

### Task 7: ForgotPasswordScreen — inline email validation

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/ForgotPasswordScreen.kt`

**Step 1: Add imports and error state**

In `FormContent`, add:
```kotlin
import com.iams.app.ui.utils.InputValidation
import com.iams.app.ui.utils.InputSanitizer
```

After `var email by remember { mutableStateOf("") }`, add:
```kotlin
    var emailError by remember { mutableStateOf<String?>(null) }
```

**Step 2: Add submit validation wrapper**

Add before the `Spacer`:
```kotlin
    fun submit() {
        val err = InputValidation.validateEmail(email)
        emailError = err
        if (err != null) return
        focusManager.clearFocus()
        onSubmit(InputSanitizer.email(email))
    }
```

**Step 3: Wire error to field**

```kotlin
    IAMSTextField(
        value = email,
        onValueChange = {
            email = it
            emailError = null
            viewModel.clearError()
        },
        label = "Email",
        placeholder = "your.email@example.com",
        enabled = !uiState.isLoading,
        error = emailError,
        keyboardOptions = KeyboardOptions(
            keyboardType = KeyboardType.Email,
            imeAction = ImeAction.Done
        ),
        keyboardActions = KeyboardActions(
            onDone = { submit() }
        )
    )
```

**Step 4: Update button to use submit()**

```kotlin
    IAMSButton(
        text = "Send Reset Link",
        onClick = { submit() },
        // ... rest unchanged
    )
```

**Step 5: Verify and commit**

Run: `cd android && ./gradlew compileDebugKotlin 2>&1 | tail -5`

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/ForgotPasswordScreen.kt
git commit -m "feat(android): add inline email validation to ForgotPasswordScreen"
```

---

### Task 8: ResetPasswordScreen — inline password validation

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/ResetPasswordScreen.kt`

**Step 1: Add imports and error state to FormContent**

```kotlin
import com.iams.app.ui.utils.InputValidation
```

After `var confirmPassword by remember { mutableStateOf("") }`, add:
```kotlin
    var passwordError by remember { mutableStateOf<String?>(null) }
    var confirmPasswordError by remember { mutableStateOf<String?>(null) }
```

**Step 2: Add submit validation wrapper**

```kotlin
    fun submit() {
        val pErr = InputValidation.validatePassword(password)
        val cErr = InputValidation.validatePasswordMatch(password, confirmPassword)
        passwordError = pErr
        confirmPasswordError = cErr
        if (pErr != null || cErr != null) return
        focusManager.clearFocus()
        onSubmit(password, confirmPassword)
    }
```

**Step 3: Wire error state to fields**

New Password field — change `error = null` to `error = passwordError`:
```kotlin
    IAMSTextField(
        value = password,
        onValueChange = {
            password = it
            passwordError = null
            viewModel.clearError()
        },
        label = "New Password",
        placeholder = "At least 8 characters",
        isPassword = true,
        enabled = !uiState.isLoading,
        error = passwordError,
        keyboardOptions = KeyboardOptions(
            keyboardType = KeyboardType.Password,
            imeAction = ImeAction.Next
        )
    )
```

Confirm Password field — change `error = null` to `error = confirmPasswordError`:
```kotlin
    IAMSTextField(
        value = confirmPassword,
        onValueChange = {
            confirmPassword = it
            confirmPasswordError = null
            viewModel.clearError()
        },
        label = "Confirm Password",
        placeholder = "Confirm new password",
        isPassword = true,
        enabled = !uiState.isLoading,
        error = confirmPasswordError,
        keyboardOptions = KeyboardOptions(
            keyboardType = KeyboardType.Password,
            imeAction = ImeAction.Done
        ),
        keyboardActions = KeyboardActions(
            onDone = { submit() }
        )
    )
```

**Step 4: Update button to use submit()**

```kotlin
    IAMSButton(
        text = "Reset Password",
        onClick = { submit() },
        // ... rest unchanged
    )
```

**Step 5: Verify and commit**

Run: `cd android && ./gradlew compileDebugKotlin 2>&1 | tail -5`

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/ResetPasswordScreen.kt
git commit -m "feat(android): add inline password validation to ResetPasswordScreen"
```

---

### Task 9: FacultyManualEntryScreen — switch to IAMSTextField

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyManualEntryScreen.kt`

**Step 1: Add imports**

```kotlin
import com.iams.app.ui.components.IAMSTextField
import com.iams.app.ui.utils.InputSanitizer
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardCapitalization
```

Remove unused imports that were only needed for raw BasicTextField decoration:
```kotlin
// Remove these if no longer used:
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.ui.graphics.SolidColor
```

**Step 2: Replace Student ID BasicTextField with IAMSTextField**

Replace the entire Student ID section (label Text + BasicTextField + error Text, approximately lines 132-179) with:
```kotlin
            // Student ID field
            IAMSTextField(
                value = uiState.studentId,
                onValueChange = { viewModel.updateStudentId(it) },
                label = "Student ID",
                placeholder = "e.g. 21-A-012345",
                error = uiState.studentIdError,
                keyboardOptions = KeyboardOptions(
                    capitalization = KeyboardCapitalization.Characters
                ),
            )
```

**Step 3: Replace Remarks BasicTextField with IAMSTextField**

Replace the Remarks section (label Text + BasicTextField, approximately lines 239-271) with:
```kotlin
            // Remarks field
            IAMSTextField(
                value = uiState.remarks,
                onValueChange = { viewModel.updateRemarks(it) },
                label = "Remarks",
                placeholder = "Optional remarks (e.g., reason for manual entry)",
                singleLine = false,
                modifier = Modifier.height(88.dp),
                maxLength = 500,
            )
```

Note: `singleLine = false` is already supported by IAMSTextField. The height override via modifier handles the multiline height. `maxLength = 500` prevents abuse.

**Step 4: Add sanitization to submit**

In `FacultyManualEntryViewModel.submit()`, sanitize before API call:
```kotlin
        val sanitizedId = InputSanitizer.studentId(state.studentId)
        val sanitizedRemarks = InputSanitizer.trimmed(state.remarks)
```

Use `sanitizedId` and `sanitizedRemarks` in the `ManualEntryRequest`.

**Step 5: Clean up unused imports**

Remove imports no longer needed after switching to IAMSTextField:
- `BasicTextField` (if no longer used)
- `SolidColor` (if no longer used)
- Check each removed import individually

**Step 6: Verify and commit**

Run: `cd android && ./gradlew compileDebugKotlin 2>&1 | tail -5`

```bash
git add android/app/src/main/java/com/iams/app/ui/faculty/FacultyManualEntryScreen.kt
git add android/app/src/main/java/com/iams/app/ui/faculty/FacultyManualEntryViewModel.kt
git commit -m "feat(android): switch FacultyManualEntry to IAMSTextField + sanitization"
```

---

### Task 10: Refactor profile ViewModels to use InputValidation

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/student/StudentEditProfileViewModel.kt`
- Modify: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyEditProfileViewModel.kt`

**Step 1: Refactor StudentEditProfileViewModel.saveProfile()**

Add import:
```kotlin
import com.iams.app.ui.utils.InputValidation
import com.iams.app.ui.utils.InputSanitizer
```

Replace the inline validation in `saveProfile()` with:
```kotlin
    fun saveProfile() {
        val state = _uiState.value
        val emailErr = InputValidation.validateEmail(state.email)
        val phoneErr = InputValidation.validatePhone(state.phone)

        if (emailErr != null || phoneErr != null) {
            _uiState.value = state.copy(emailError = emailErr, phoneError = phoneErr)
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isSavingProfile = true,
                profileSuccess = null,
                profileError = null
            )

            try {
                val response = apiService.updateProfile(
                    UpdateProfileRequest(
                        email = InputSanitizer.email(state.email),
                        phone = InputSanitizer.trimmed(state.phone)
                    )
                )
                // ... rest unchanged
```

Replace inline validation in `changePassword()` with:
```kotlin
    fun changePassword() {
        val state = _uiState.value
        val currentErr = InputValidation.validateRequired(state.currentPassword, "Current password")
        val newErr = InputValidation.validatePassword(state.newPassword)
        val confirmErr = InputValidation.validatePasswordMatch(state.newPassword, state.confirmPassword)

        if (currentErr != null || newErr != null || confirmErr != null) {
            _uiState.value = state.copy(
                currentPasswordError = currentErr,
                newPasswordError = newErr,
                confirmPasswordError = confirmErr
            )
            return
        }
        // ... rest unchanged (launch coroutine)
```

**Step 2: Refactor FacultyEditProfileViewModel similarly**

Add same imports. Replace `saveProfile()` validation:
```kotlin
    fun saveProfile() {
        val state = _uiState.value
        val emailErr = InputValidation.validateEmail(state.email)
        val phoneErr = InputValidation.validatePhoneOptional(state.phone)

        if (emailErr != null || phoneErr != null) {
            _uiState.value = _uiState.value.copy(emailError = emailErr, phoneError = phoneErr)
            return
        }
        // ... rest unchanged
```

Note: Faculty uses `validatePhoneOptional` since phone is not required for faculty.

Replace `changePassword()` validation same pattern as Student.

In `saveProfile()` API call, apply sanitization:
```kotlin
                val request = UpdateProfileRequest(
                    email = InputSanitizer.email(state.email),
                    phone = InputSanitizer.trimmed(state.phone).ifBlank { null },
                )
```

**Step 3: Verify and commit**

Run: `cd android && ./gradlew compileDebugKotlin 2>&1 | tail -5`

```bash
git add android/app/src/main/java/com/iams/app/ui/student/StudentEditProfileViewModel.kt
git add android/app/src/main/java/com/iams/app/ui/faculty/FacultyEditProfileViewModel.kt
git commit -m "refactor(android): use centralized InputValidation in profile ViewModels"
```

---

### Task 11: Final build verification

**Step 1: Full debug build**

Run: `cd android && ./gradlew assembleDebug 2>&1 | tail -10`
Expected: BUILD SUCCESSFUL

**Step 2: Review all changed files for consistency**

Run: `git diff --stat HEAD~10` to verify only expected files changed.

Spot-check:
- Every `IAMSTextField` with a password field has `error = <something>` (not `error = null`)
- Every form submit calls `InputValidation` before API calls
- Every API call uses `InputSanitizer` for email/studentId inputs
- No remaining raw `BasicTextField` usage in auth/profile/manual-entry screens
- No remaining Toast calls for field-specific validation errors

**Step 3: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "fix(android): final consistency fixes for input validation"
```

---

## Lessons

- Registration used 6-char min password while all other screens used 8 — easy to miss when validation is scattered across files.
- Raw `BasicTextField` in one screen while every other screen uses the shared component creates visual drift that's hard to catch in review.
- Toast-only errors on auth screens make it impossible for users to know which field has the problem.
- Android project has no test infrastructure — adding JUnit for pure utility functions would be a worthwhile follow-up task.
