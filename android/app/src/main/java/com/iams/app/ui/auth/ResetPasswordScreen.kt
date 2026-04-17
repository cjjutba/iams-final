package com.iams.app.ui.auth

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.AuthLayout
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSTextField
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.PasswordMatchIndicator
import com.iams.app.ui.components.PasswordStrengthMeter
import com.iams.app.ui.components.ToastType
import com.iams.app.ui.utils.InputSanitizer
import com.iams.app.ui.utils.InputValidation
import com.iams.app.ui.utils.PasswordPolicy
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextSecondary

@Composable
fun ResetPasswordScreen(
    navController: NavController,
    viewModel: ResetPasswordViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
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

    AuthLayout(
        showBack = true,
        title = if (uiState.success) "Password Updated" else "Set New Password",
        subtitle = if (uiState.success) "Your password has been changed successfully" else "Choose a strong password for your account",
        onBack = { navController.popBackStack() }
    ) {
        if (uiState.success) {
            SuccessContent(
                onGoToLogin = {
                    navController.navigate(Routes.WELCOME) {
                        popUpTo(Routes.WELCOME) { inclusive = true }
                    }
                }
            )
        } else {
            FormContent(
                uiState = uiState,
                viewModel = viewModel,
                onSubmit = { password, confirmPassword ->
                    viewModel.resetPassword(password, confirmPassword)
                }
            )
        }
    }
}

@Composable
private fun FormContent(
    uiState: ResetPasswordUiState,
    viewModel: ResetPasswordViewModel,
    onSubmit: (String, String) -> Unit
) {
    var password by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var passwordError by remember { mutableStateOf<String?>(null) }
    var confirmPasswordError by remember { mutableStateOf<String?>(null) }
    var passwordTouched by remember { mutableStateOf(false) }
    var confirmTouched by remember { mutableStateOf(false) }
    val focusManager = LocalFocusManager.current

    val evaluation by remember(password) {
        derivedStateOf { PasswordPolicy.evaluate(password) }
    }

    val liveConfirmError by remember(password, confirmPassword, confirmTouched) {
        derivedStateOf {
            if (!confirmTouched || confirmPassword.isEmpty()) null
            else if (password != confirmPassword) "Passwords do not match"
            else null
        }
    }

    val formValid by remember(password, confirmPassword, evaluation) {
        derivedStateOf {
            evaluation.isValid && confirmPassword.isNotEmpty() && password == confirmPassword
        }
    }

    fun submit() {
        val sanitized = InputSanitizer.password(password)
        val pErr = InputValidation.validatePassword(sanitized)
        val cErr = InputValidation.validatePasswordMatch(sanitized, confirmPassword)
        passwordError = pErr
        confirmPasswordError = cErr
        passwordTouched = true
        confirmTouched = true
        if (pErr != null || cErr != null) return
        focusManager.clearFocus()
        onSubmit(sanitized, confirmPassword)
    }

    Spacer(modifier = Modifier.height(32.dp))

    // New Password field — unified policy + real-time feedback below
    IAMSTextField(
        value = password,
        onValueChange = {
            password = it
            passwordTouched = true
            passwordError = null
            viewModel.clearError()
        },
        label = "New Password",
        placeholder = "At least 8 characters",
        isPassword = true,
        enabled = !uiState.isLoading,
        error = if (passwordTouched) passwordError else null,
        supportingText = PasswordPolicy.REQUIREMENTS_TEXT,
        keyboardOptions = KeyboardOptions(
            keyboardType = KeyboardType.Password,
            imeAction = ImeAction.Next
        )
    )

    if (password.isNotEmpty() || passwordTouched) {
        Spacer(modifier = Modifier.height(12.dp))
        PasswordStrengthMeter(evaluation = evaluation)
    }

    Spacer(modifier = Modifier.height(20.dp))

    // Confirm Password field
    IAMSTextField(
        value = confirmPassword,
        onValueChange = {
            confirmPassword = it
            confirmTouched = true
            confirmPasswordError = null
            viewModel.clearError()
        },
        label = "Confirm Password",
        placeholder = "Confirm new password",
        isPassword = true,
        enabled = !uiState.isLoading,
        error = confirmPasswordError ?: liveConfirmError,
        keyboardOptions = KeyboardOptions(
            keyboardType = KeyboardType.Password,
            imeAction = ImeAction.Done
        ),
        keyboardActions = KeyboardActions(
            onDone = { submit() }
        )
    )

    if (confirmPassword.isNotEmpty()) {
        Spacer(modifier = Modifier.height(8.dp))
        PasswordMatchIndicator(
            password = password,
            confirmPassword = confirmPassword,
        )
    }

    Spacer(modifier = Modifier.height(16.dp))

    // Submit button
    IAMSButton(
        text = "Reset Password",
        onClick = { submit() },
        size = IAMSButtonSize.LG,
        enabled = !uiState.isLoading && formValid,
        isLoading = uiState.isLoading,
        loadingText = "Resetting..."
    )
}

@Composable
private fun SuccessContent(onGoToLogin: () -> Unit) {
    Spacer(modifier = Modifier.height(32.dp))

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Check icon
        Icon(
            imageVector = Icons.Outlined.CheckCircle,
            contentDescription = "Success",
            modifier = Modifier.size(56.dp),
            tint = PresentFg
        )

        Spacer(modifier = Modifier.height(24.dp))

        // Title
        Text(
            text = "Password Reset Complete",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
            color = Primary
        )

        Spacer(modifier = Modifier.height(16.dp))

        // Message
        Text(
            text = "Your password has been updated. You can now sign in with your new password.",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(modifier = Modifier.height(24.dp))

        // Go to Login button
        IAMSButton(
            text = "Go to Login",
            onClick = onGoToLogin,
            size = IAMSButtonSize.LG
        )
    }
}
