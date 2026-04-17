# Toast System Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire toast notifications into every screen that has user-facing actions (login, registration, password reset, data loading errors) so users always get visual feedback.

**Architecture:** Use the existing `IAMSToast` infrastructure (`ToastState`, `LocalToastState`, `IAMSToastHost` — already provided at root). Each screen gets a `LaunchedEffect` that watches ViewModel state fields and calls `toastState.showToast()`. This matches the existing pattern in `FacultyEditProfileScreen` and `StudentEditProfileScreen`. No new infrastructure needed.

**Tech Stack:** Kotlin, Jetpack Compose, existing `IAMSToast.kt` component

---

### Task 1: LoginViewModel — Add Toast Events for Success and Error

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/LoginViewModel.kt`

**Step 1: Add `successMessage` field to `LoginUiState`**

In `LoginUiState`, add a `successMessage` field. In the `login()` function, set it on success. This gives the screen something to observe for showing a success toast.

```kotlin
data class LoginUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val loginSuccess: Boolean = false,
    val userRole: String? = null,
    val successMessage: String? = null
)
```

In `login()`, on success branch, add `successMessage = "Welcome back!"`:

```kotlin
_uiState.value = _uiState.value.copy(
    isLoading = false,
    loginSuccess = true,
    userRole = body.user.role,
    successMessage = "Welcome back!"
)
```

Add a `clearSuccessMessage()` method:

```kotlin
fun clearSuccessMessage() {
    _uiState.value = _uiState.value.copy(successMessage = null)
}
```

**Step 2: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/LoginViewModel.kt
git commit -m "feat: add successMessage to LoginUiState for toast integration"
```

---

### Task 2: StudentLoginScreen — Wire Toast for Success and Error

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/StudentLoginScreen.kt`

**Step 1: Add toast imports and observers**

Add imports at the top:

```kotlin
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
```

Inside the composable, before the existing `LaunchedEffect(uiState.loginSuccess)`, add:

```kotlin
val toastState = LocalToastState.current

// Toast on success
LaunchedEffect(uiState.successMessage) {
    uiState.successMessage?.let {
        toastState.showToast(it, ToastType.SUCCESS)
        viewModel.clearSuccessMessage()
    }
}

// Toast on error
LaunchedEffect(uiState.error) {
    uiState.error?.let {
        toastState.showToast(it, ToastType.ERROR)
        viewModel.clearError()
    }
}
```

**Step 2: Remove inline error from password TextField**

Change the password `IAMSTextField` from `error = uiState.error` to `error = null`:

```kotlin
IAMSTextField(
    value = password,
    onValueChange = {
        password = it
        viewModel.clearError()
    },
    label = "Password",
    placeholder = "Enter your password",
    isPassword = true,
    enabled = !uiState.isLoading,
    error = null,  // was: uiState.error — now shown via toast
    ...
)
```

**Step 3: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/StudentLoginScreen.kt
git commit -m "feat: wire toast notifications to StudentLoginScreen"
```

---

### Task 3: FacultyLoginScreen — Wire Toast for Success and Error

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/FacultyLoginScreen.kt`

**Step 1: Add toast imports and observers**

Same pattern as StudentLoginScreen. Add imports:

```kotlin
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
```

Inside composable, add:

```kotlin
val toastState = LocalToastState.current

LaunchedEffect(uiState.successMessage) {
    uiState.successMessage?.let {
        toastState.showToast(it, ToastType.SUCCESS)
        viewModel.clearSuccessMessage()
    }
}

LaunchedEffect(uiState.error) {
    uiState.error?.let {
        toastState.showToast(it, ToastType.ERROR)
        viewModel.clearError()
    }
}
```

**Step 2: Remove inline error from password TextField**

Change `error = uiState.error` to `error = null` on the password field.

**Step 3: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/FacultyLoginScreen.kt
git commit -m "feat: wire toast notifications to FacultyLoginScreen"
```

---

### Task 4: RegistrationViewModel — Add Toast State Fields

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/RegistrationViewModel.kt`

**Step 1: Add toast-related fields to RegistrationUiState**

Add `resendSuccess` and `successMessage` fields:

```kotlin
data class RegistrationUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    // Step 1 results
    val studentVerified: Boolean = false,
    val studentId: String = "",
    val firstName: String = "",
    val lastName: String = "",
    // Step 2 results
    val registrationComplete: Boolean = false,
    val registeredEmail: String = "",
    // Email verification
    val emailVerified: Boolean = false,
    val isPolling: Boolean = false,
    val resendSuccess: Boolean = false,
    // Step 3 face capture
    val capturedFaces: List<Bitmap> = emptyList(),
    // Review / upload
    val isUploading: Boolean = false,
    val uploadSuccess: Boolean = false,
    val uploadError: String? = null,
)
```

**Step 2: Emit resendSuccess on successful resend**

In `resendVerificationEmail()`, on success branch, set `resendSuccess = true`:

```kotlin
if (response.isSuccessful) {
    _uiState.value = _uiState.value.copy(
        isLoading = false,
        error = null,
        resendSuccess = true
    )
}
```

**Step 3: Add clearResendSuccess method**

```kotlin
fun clearResendSuccess() {
    _uiState.value = _uiState.value.copy(resendSuccess = false)
}
```

**Step 4: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/RegistrationViewModel.kt
git commit -m "feat: add resendSuccess state to RegistrationViewModel for toast"
```

---

### Task 5: RegisterStep1Screen — Wire Toast

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/RegisterStep1Screen.kt`

**Step 1: Add toast observers**

Add imports:

```kotlin
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
```

Inside composable, add before the existing `LaunchedEffect(uiState.studentVerified)`:

```kotlin
val toastState = LocalToastState.current

// Toast on successful verification
LaunchedEffect(uiState.studentVerified) {
    if (uiState.studentVerified) {
        toastState.showToast("Student ID verified", ToastType.SUCCESS)
    }
}

// Toast on error
LaunchedEffect(uiState.error) {
    uiState.error?.let {
        toastState.showToast(it, ToastType.ERROR)
        viewModel.clearError()
    }
}
```

**Step 2: Remove inline error from birthdate TextField**

Change the birthdate field from `error = uiState.error` to `error = null`.

**Step 3: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/RegisterStep1Screen.kt
git commit -m "feat: wire toast notifications to RegisterStep1Screen"
```

---

### Task 6: RegisterStep2Screen — Wire Toast

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/RegisterStep2Screen.kt`

**Step 1: Add toast observers**

Add imports:

```kotlin
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
```

Inside composable, add:

```kotlin
val toastState = LocalToastState.current

// Toast on successful registration
LaunchedEffect(uiState.registrationComplete) {
    if (uiState.registrationComplete) {
        toastState.showToast("Account created! Check your email.", ToastType.SUCCESS)
    }
}

// Toast on error (from ViewModel or local validation)
LaunchedEffect(uiState.error) {
    uiState.error?.let {
        toastState.showToast(it, ToastType.ERROR)
        viewModel.clearError()
    }
}
```

**Step 2: Handle local validation errors via toast**

In the `attemptRegister()` function, instead of setting `localError`, show toast directly. Replace the `localError = "..."` assignments:

```kotlin
fun attemptRegister() {
    if (email.isBlank() || password.isBlank() || confirmPassword.isBlank()) {
        toastState.showToast("Please fill in all fields", ToastType.ERROR)
        return
    }
    if (password != confirmPassword) {
        toastState.showToast("Passwords do not match", ToastType.ERROR)
        return
    }
    if (password.length < 6) {
        toastState.showToast("Password must be at least 6 characters", ToastType.ERROR)
        return
    }
    viewModel.register(...)
}
```

Remove the `localError` state variable and the `displayError` combination. Change the confirm password field from `error = displayError` to `error = null`.

**Step 3: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/RegisterStep2Screen.kt
git commit -m "feat: wire toast notifications to RegisterStep2Screen"
```

---

### Task 7: EmailVerificationScreen — Wire Toast

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/EmailVerificationScreen.kt`

**Step 1: Add toast observers**

Add imports:

```kotlin
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
```

Inside composable, add:

```kotlin
val toastState = LocalToastState.current

// Toast on email verified
LaunchedEffect(uiState.emailVerified) {
    if (uiState.emailVerified) {
        toastState.showToast("Email verified!", ToastType.SUCCESS)
    }
}

// Toast on resend success
LaunchedEffect(uiState.resendSuccess) {
    if (uiState.resendSuccess) {
        toastState.showToast("Verification email sent!", ToastType.SUCCESS)
        viewModel.clearResendSuccess()
    }
}

// Toast on error
LaunchedEffect(uiState.error) {
    uiState.error?.let {
        toastState.showToast(it, ToastType.ERROR)
        viewModel.clearError()
    }
}
```

**Step 2: Remove inline error Text**

Remove the block (lines 165-174):

```kotlin
// Error message
if (uiState.error != null) {
    Spacer(modifier = Modifier.height(12.dp))
    Text(
        text = uiState.error!!,
        color = MaterialTheme.colorScheme.error,
        style = MaterialTheme.typography.bodySmall,
        textAlign = TextAlign.Center
    )
}
```

**Step 3: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/EmailVerificationScreen.kt
git commit -m "feat: wire toast notifications to EmailVerificationScreen"
```

---

### Task 8: RegisterStep3Screen — Toast on Face Capture

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/RegisterStep3Screen.kt`

**Step 1: Add toast on capture**

Add imports:

```kotlin
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
```

Inside composable, add:

```kotlin
val toastState = LocalToastState.current
```

In the `FaceCaptureView`'s `onCapture` callback, after `viewModel.addCapturedFace(bitmap)`, add:

```kotlin
onCapture = { bitmap ->
    viewModel.addCapturedFace(bitmap)
    captureIndex = capturedCount + 1
    toastState.showToast("Photo ${capturedCount + 1} captured", ToastType.INFO)
}
```

**Step 2: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/RegisterStep3Screen.kt
git commit -m "feat: wire toast notification to RegisterStep3Screen on face capture"
```

---

### Task 9: RegisterReviewScreen — Wire Toast for Upload

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/RegisterReviewScreen.kt`

**Step 1: Add toast observers**

Add imports:

```kotlin
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
```

Inside composable, add:

```kotlin
val toastState = LocalToastState.current

// Toast on upload success
LaunchedEffect(uiState.uploadSuccess) {
    if (uiState.uploadSuccess) {
        toastState.showToast("Face registration complete!", ToastType.SUCCESS)
    }
}

// Toast on upload error
LaunchedEffect(uiState.uploadError) {
    uiState.uploadError?.let {
        toastState.showToast(it, ToastType.ERROR)
        viewModel.clearUploadError()
    }
}
```

**Step 2: Remove inline error Text**

Remove the block (lines 241-250):

```kotlin
// Error message
if (uiState.uploadError != null) {
    Text(
        text = uiState.uploadError!!,
        color = MaterialTheme.colorScheme.error,
        style = MaterialTheme.typography.bodySmall,
        textAlign = TextAlign.Center,
        modifier = Modifier.fillMaxWidth()
    )
    Spacer(modifier = Modifier.height(8.dp))
}
```

**Step 3: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/RegisterReviewScreen.kt
git commit -m "feat: wire toast notifications to RegisterReviewScreen"
```

---

### Task 10: ForgotPasswordScreen — Wire Toast

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/ForgotPasswordScreen.kt`
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/ForgotPasswordViewModel.kt` (need to check for `successMessage` field)

**Step 1: Add toast observers to ForgotPasswordScreen**

Add imports:

```kotlin
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
```

Inside `ForgotPasswordScreen`, add:

```kotlin
val toastState = LocalToastState.current

// Toast on success
LaunchedEffect(uiState.success) {
    if (uiState.success) {
        toastState.showToast("Reset link sent to your email", ToastType.SUCCESS)
    }
}

// Toast on error
LaunchedEffect(uiState.error) {
    uiState.error?.let {
        toastState.showToast(it, ToastType.ERROR)
        viewModel.clearError()
    }
}
```

**Step 2: Remove inline error from email TextField**

In `FormContent`, change `error = uiState.error` to `error = null`.

Note: Pass `toastState` to `FormContent` or restructure. Since `FormContent` is a private composable, the simplest approach is to get `toastState` inside `FormContent` via `LocalToastState.current` directly, or move the local validation toasts to the ViewModel.

Actually, the cleanest approach: keep the toast observers in the top-level `ForgotPasswordScreen` and just remove `error = uiState.error` from the TextField in `FormContent`.

**Step 3: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/ForgotPasswordScreen.kt
git commit -m "feat: wire toast notifications to ForgotPasswordScreen"
```

---

### Task 11: ResetPasswordScreen — Wire Toast

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/auth/ResetPasswordScreen.kt`

**Step 1: Add toast observers**

Add imports:

```kotlin
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
```

Inside `ResetPasswordScreen`, add:

```kotlin
val toastState = LocalToastState.current

LaunchedEffect(uiState.success) {
    if (uiState.success) {
        toastState.showToast("Password reset successfully", ToastType.SUCCESS)
    }
}

LaunchedEffect(uiState.error) {
    uiState.error?.let {
        toastState.showToast(it, ToastType.ERROR)
        viewModel.clearError()
    }
}
```

**Step 2: Remove inline error from confirm password TextField**

In `FormContent`, change `error = uiState.error` to `error = null`.

**Step 3: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/auth/ResetPasswordScreen.kt
git commit -m "feat: wire toast notifications to ResetPasswordScreen"
```

---

### Task 12: Data Screens — Wire Error Toasts

**Files:**
- Modify: `android/app/src/main/java/com/iams/app/ui/student/StudentHomeScreen.kt`
- Modify: `android/app/src/main/java/com/iams/app/ui/student/StudentHistoryScreen.kt`
- Modify: `android/app/src/main/java/com/iams/app/ui/student/StudentScheduleScreen.kt`
- Modify: `android/app/src/main/java/com/iams/app/ui/student/StudentProfileScreen.kt`
- Modify: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyProfileScreen.kt`
- Modify: `android/app/src/main/java/com/iams/app/ui/faculty/FacultyReportsScreen.kt`

**Step 1: Add error toast to each screen**

For each screen, add at the top of the composable function:

```kotlin
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
```

And inside the composable:

```kotlin
val toastState = LocalToastState.current

LaunchedEffect(uiState.error) {
    uiState.error?.let {
        toastState.showToast(it, ToastType.ERROR)
        viewModel.clearError()
    }
}
```

Notes per screen:
- **StudentHomeScreen**: ViewModel has `clearError()` — use it
- **StudentHistoryScreen**: ViewModel has `clearError()` — use it
- **StudentScheduleScreen**: ViewModel has `clearError()` — use it
- **StudentProfileScreen**: ViewModel may not have `clearError()` — add one if missing (set `error = null`)
- **FacultyProfileScreen**: ViewModel may not have `clearError()` — add one if missing
- **FacultyReportsScreen**: Already imports `LocalToastState` and gets `toastState`. Just add the `LaunchedEffect(uiState.error)` block. ViewModel may not have `clearError()` — add one if missing.

**Step 2: Add `clearError()` to ViewModels that lack it**

Check each ViewModel. If it doesn't have `clearError()`, add:

```kotlin
fun clearError() {
    _uiState.value = _uiState.value.copy(error = null)
}
```

**Step 3: Commit**

```bash
git add android/app/src/main/java/com/iams/app/ui/student/StudentHomeScreen.kt \
        android/app/src/main/java/com/iams/app/ui/student/StudentHistoryScreen.kt \
        android/app/src/main/java/com/iams/app/ui/student/StudentScheduleScreen.kt \
        android/app/src/main/java/com/iams/app/ui/student/StudentProfileScreen.kt \
        android/app/src/main/java/com/iams/app/ui/faculty/FacultyProfileScreen.kt \
        android/app/src/main/java/com/iams/app/ui/faculty/FacultyReportsScreen.kt
git add android/app/src/main/java/com/iams/app/ui/student/StudentProfileViewModel.kt \
        android/app/src/main/java/com/iams/app/ui/faculty/FacultyProfileViewModel.kt \
        android/app/src/main/java/com/iams/app/ui/faculty/FacultyReportsViewModel.kt
git commit -m "feat: wire error toast notifications to data screens"
```

---

### Task 13: Build Verification

**Step 1: Run Android build to verify compilation**

```bash
cd android && ./gradlew assembleDebug
```

Expected: BUILD SUCCESSFUL. If there are compilation errors, fix them.

**Step 2: Final commit if any fixes needed**

---

### Summary of All Changes

| File | Change |
|------|--------|
| `LoginViewModel.kt` | Add `successMessage` field + `clearSuccessMessage()` |
| `RegistrationViewModel.kt` | Add `resendSuccess` field + `clearResendSuccess()` |
| `StudentLoginScreen.kt` | Add toast LaunchedEffects, remove inline error |
| `FacultyLoginScreen.kt` | Add toast LaunchedEffects, remove inline error |
| `RegisterStep1Screen.kt` | Add toast LaunchedEffects, remove inline error |
| `RegisterStep2Screen.kt` | Add toast LaunchedEffects, remove localError pattern |
| `RegisterStep3Screen.kt` | Add toast on face capture |
| `EmailVerificationScreen.kt` | Add toast LaunchedEffects, remove inline error Text |
| `RegisterReviewScreen.kt` | Add toast LaunchedEffects, remove inline error Text |
| `ForgotPasswordScreen.kt` | Add toast LaunchedEffects, remove inline error |
| `ResetPasswordScreen.kt` | Add toast LaunchedEffects, remove inline error |
| `StudentHomeScreen.kt` | Add error toast LaunchedEffect |
| `StudentHistoryScreen.kt` | Add error toast LaunchedEffect |
| `StudentScheduleScreen.kt` | Add error toast LaunchedEffect |
| `StudentProfileScreen.kt` | Add error toast LaunchedEffect |
| `FacultyProfileScreen.kt` | Add error toast LaunchedEffect |
| `FacultyReportsScreen.kt` | Add error toast LaunchedEffect |
| Various ViewModels | Add `clearError()` where missing |
