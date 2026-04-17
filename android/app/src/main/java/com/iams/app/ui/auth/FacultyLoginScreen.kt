package com.iams.app.ui.auth

import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.platform.LocalFocusManager
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
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.utils.InputSanitizer
import com.iams.app.ui.utils.InputValidation

@Composable
fun FacultyLoginScreen(
    navController: NavController,
    viewModel: LoginViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var emailError by remember { mutableStateOf<String?>(null) }
    var passwordError by remember { mutableStateOf<String?>(null) }
    val focusManager = LocalFocusManager.current

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

    // Navigate on successful login
    LaunchedEffect(uiState.loginSuccess) {
        if (uiState.loginSuccess) {
            navController.navigate(Routes.FACULTY_HOME) {
                popUpTo(Routes.WELCOME) { inclusive = true }
            }
        }
    }

    fun submit() {
        val eErr = InputValidation.validateEmail(email)
        val pErr = InputValidation.validateRequired(password, "Password")
        emailError = eErr
        passwordError = pErr
        if (eErr != null || pErr != null) return
        focusManager.clearFocus()
        viewModel.login(InputSanitizer.email(email), InputSanitizer.password(password))
    }

    AuthLayout(
        showBack = true,
        title = "Welcome, Faculty!",
        subtitle = "Sign in to continue",
        onBack = { navController.popBackStack() }
    ) {
        // Form section top margin
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
                imeAction = ImeAction.Next
            ),
            keyboardActions = KeyboardActions(
                onNext = { focusManager.moveFocus(FocusDirection.Down) }
            )
        )

        Spacer(modifier = Modifier.height(20.dp))

        // Password field
        IAMSTextField(
            value = password,
            onValueChange = {
                password = it
                passwordError = null
                viewModel.clearError()
            },
            label = "Password",
            placeholder = "Enter your password",
            isPassword = true,
            enabled = !uiState.isLoading,
            error = passwordError,
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Done
            ),
            keyboardActions = KeyboardActions(
                onDone = { submit() }
            )
        )

        Spacer(modifier = Modifier.height(8.dp))

        // Login button
        IAMSButton(
            text = "Sign In",
            onClick = { submit() },
            size = IAMSButtonSize.LG,
            enabled = !uiState.isLoading,
            isLoading = uiState.isLoading,
            loadingText = "Signing in..."
        )

        Spacer(modifier = Modifier.height(32.dp))

        // Faculty notice
        Text(
            text = "Faculty accounts are created by administrator",
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth()
        )
    }
}
