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
import com.iams.app.ui.utils.InputSanitizer
import com.iams.app.ui.utils.InputValidation
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

@Composable
fun ForgotPasswordScreen(
    navController: NavController,
    viewModel: ForgotPasswordViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
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

    AuthLayout(
        showBack = true,
        title = if (uiState.success) null else "Reset Password",
        subtitle = if (uiState.success) null else "Enter your email to receive reset instructions",
        onBack = { navController.popBackStack() }
    ) {
        if (uiState.success) {
            SuccessContent()
        } else {
            FormContent(
                uiState = uiState,
                viewModel = viewModel,
                onSubmit = { email -> viewModel.forgotPassword(email) }
            )
        }
    }
}

@Composable
private fun FormContent(
    uiState: ForgotPasswordUiState,
    viewModel: ForgotPasswordViewModel,
    onSubmit: (String) -> Unit
) {
    var email by remember { mutableStateOf("") }
    var emailError by remember { mutableStateOf<String?>(null) }
    val focusManager = LocalFocusManager.current

    fun submit() {
        val err = InputValidation.validateEmail(email)
        emailError = err
        if (err != null) return
        focusManager.clearFocus()
        onSubmit(InputSanitizer.email(email))
    }

    Spacer(modifier = Modifier.height(32.dp))

    // Email field
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

    Spacer(modifier = Modifier.height(20.dp))

    Spacer(modifier = Modifier.height(8.dp))

    // Submit button
    IAMSButton(
        text = "Send Reset Link",
        onClick = { submit() },
        size = IAMSButtonSize.LG,
        enabled = !uiState.isLoading,
        isLoading = uiState.isLoading,
        loadingText = "Sending..."
    )
}

@Composable
private fun SuccessContent() {
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
            text = "Reset link sent!",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
            color = Primary
        )

        Spacer(modifier = Modifier.height(16.dp))

        // Message
        Text(
            text = "We sent password reset instructions to your email. Follow the link in your inbox to continue.",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(modifier = Modifier.height(8.dp))

        // Hint
        Text(
            text = "If you do not see the email, check spam or try again after a few minutes.",
            style = MaterialTheme.typography.bodySmall,
            color = TextTertiary,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth()
        )
    }
}
