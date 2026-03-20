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
import com.iams.app.ui.components.ToastType
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
    val focusManager = LocalFocusManager.current

    Spacer(modifier = Modifier.height(32.dp))

    // New Password field
    IAMSTextField(
        value = password,
        onValueChange = {
            password = it
            viewModel.clearError()
        },
        label = "New Password",
        placeholder = "Enter new password",
        isPassword = true,
        enabled = !uiState.isLoading,
        error = null,
        keyboardOptions = KeyboardOptions(
            keyboardType = KeyboardType.Password,
            imeAction = ImeAction.Next
        )
    )

    Spacer(modifier = Modifier.height(20.dp))

    // Confirm Password field
    IAMSTextField(
        value = confirmPassword,
        onValueChange = {
            confirmPassword = it
            viewModel.clearError()
        },
        label = "Confirm Password",
        placeholder = "Confirm new password",
        isPassword = true,
        enabled = !uiState.isLoading,
        error = null,
        keyboardOptions = KeyboardOptions(
            keyboardType = KeyboardType.Password,
            imeAction = ImeAction.Done
        ),
        keyboardActions = KeyboardActions(
            onDone = {
                focusManager.clearFocus()
                onSubmit(password, confirmPassword)
            }
        )
    )

    Spacer(modifier = Modifier.height(8.dp))

    // Submit button
    IAMSButton(
        text = "Reset Password",
        onClick = {
            focusManager.clearFocus()
            onSubmit(password, confirmPassword)
        },
        size = IAMSButtonSize.LG,
        enabled = !uiState.isLoading,
        isLoading = uiState.isLoading
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
