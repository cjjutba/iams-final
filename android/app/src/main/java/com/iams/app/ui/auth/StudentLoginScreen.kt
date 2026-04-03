package com.iams.app.ui.auth

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
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
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
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
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.utils.InputSanitizer
import com.iams.app.ui.utils.InputValidation

@Composable
fun StudentLoginScreen(
    navController: NavController,
    viewModel: LoginViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    var studentId by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var studentIdError by remember { mutableStateOf<String?>(null) }
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
            val destination = when (uiState.userRole) {
                "faculty" -> Routes.FACULTY_HOME
                else -> Routes.STUDENT_HOME
            }
            navController.navigate(destination) {
                popUpTo(Routes.WELCOME) { inclusive = true }
            }
        }
    }

    fun submit() {
        val idErr = InputValidation.validateStudentId(studentId)
        val pwErr = InputValidation.validateRequired(password, "Password")
        studentIdError = idErr
        passwordError = pwErr
        if (idErr != null || pwErr != null) return
        focusManager.clearFocus()
        viewModel.login(InputSanitizer.studentId(studentId), InputSanitizer.trimmed(password))
    }

    AuthLayout(
        showBack = true,
        title = "Student Login",
        subtitle = "Sign in to continue",
        onBack = { navController.popBackStack() }
    ) {
        Spacer(modifier = Modifier.height(32.dp))

        // Student ID field
        IAMSTextField(
            value = studentId,
            onValueChange = {
                studentId = it
                studentIdError = null
                viewModel.clearError()
            },
            label = "Student ID",
            placeholder = "e.g., 21-A-01234",
            enabled = !uiState.isLoading,
            error = studentIdError,
            keyboardOptions = KeyboardOptions(
                capitalization = KeyboardCapitalization.Characters,
                keyboardType = KeyboardType.Text,
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

        Spacer(modifier = Modifier.height(24.dp))

        // Login button
        IAMSButton(
            text = "Login",
            onClick = { submit() },
            size = IAMSButtonSize.LG,
            enabled = !uiState.isLoading,
            isLoading = uiState.isLoading,
            loadingText = "Signing in..."
        )

        Spacer(modifier = Modifier.height(32.dp))

        // Register link
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center
        ) {
            Text(
                text = buildAnnotatedString {
                    withStyle(SpanStyle(color = TextSecondary)) {
                        append("Don't have an account? ")
                    }
                    withStyle(SpanStyle(color = Primary, fontWeight = FontWeight.SemiBold)) {
                        append("Register")
                    }
                },
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.clickable(enabled = !uiState.isLoading) {
                    navController.navigate(Routes.REGISTER_STEP1)
                }
            )
        }
    }
}
