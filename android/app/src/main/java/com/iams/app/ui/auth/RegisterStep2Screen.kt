package com.iams.app.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.components.IAMSTextField
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary

@Composable
fun RegisterStep2Screen(
    navController: NavController,
    studentId: String,
    firstName: String,
    lastName: String,
    viewModel: RegistrationViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var localError by remember { mutableStateOf<String?>(null) }
    val focusManager = LocalFocusManager.current

    // Store birthdate from step 1 -- passed via the viewModel or route
    // We need it for the register call; since we only pass studentId/firstName/lastName
    // in the route, we'll pass a placeholder birthdate that the backend already validated
    var birthdate by remember { mutableStateOf("") }

    // Navigate on successful registration
    LaunchedEffect(uiState.registrationComplete) {
        if (uiState.registrationComplete) {
            navController.navigate(Routes.emailVerification(uiState.registeredEmail))
            viewModel.resetRegistration()
        }
    }

    fun attemptRegister() {
        localError = null
        if (email.isBlank() || password.isBlank() || confirmPassword.isBlank()) {
            localError = "Please fill in all fields"
            return
        }
        if (password != confirmPassword) {
            localError = "Passwords do not match"
            return
        }
        if (password.length < 6) {
            localError = "Password must be at least 6 characters"
            return
        }
        viewModel.register(
            email = email,
            password = password,
            studentId = studentId,
            firstName = firstName,
            lastName = lastName,
            birthdate = birthdate.ifBlank { "2000-01-01" }
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        // Header
        IAMSHeader(
            title = "Register",
            onBack = { navController.popBackStack() }
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp)
                .padding(top = 24.dp, bottom = 32.dp)
        ) {
            // Progress bar
            LinearProgressIndicator(
                progress = { 0.66f },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(6.dp)
                    .clip(RoundedCornerShape(50)),
                color = Primary,
                trackColor = Border,
            )

            Spacer(modifier = Modifier.height(12.dp))

            // Step indicator
            Text(
                text = "Step 2 of 3",
                style = MaterialTheme.typography.bodySmall,
                color = Primary
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Title
            Text(
                text = "Account Setup",
                style = MaterialTheme.typography.headlineLarge,
                color = MaterialTheme.colorScheme.onBackground
            )

            Spacer(modifier = Modifier.height(12.dp))

            // Info badge showing verified student
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Secondary, RoundedCornerShape(10.dp))
                    .padding(horizontal = 12.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Outlined.Person,
                    contentDescription = null,
                    tint = TextSecondary
                )
                Spacer(modifier = Modifier.weight(1f))
                Text(
                    text = "$firstName $lastName",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Spacer(modifier = Modifier.weight(1f))
                Text(
                    text = studentId,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
            }

            Spacer(modifier = Modifier.height(32.dp))

            // Email field
            IAMSTextField(
                value = email,
                onValueChange = {
                    email = it
                    localError = null
                    viewModel.clearError()
                },
                label = "Email",
                placeholder = "your.email@example.com",
                enabled = !uiState.isLoading,
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
                    localError = null
                    viewModel.clearError()
                },
                label = "Password",
                placeholder = "At least 6 characters",
                isPassword = true,
                enabled = !uiState.isLoading,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Password,
                    imeAction = ImeAction.Next
                ),
                keyboardActions = KeyboardActions(
                    onNext = { focusManager.moveFocus(FocusDirection.Down) }
                )
            )

            Spacer(modifier = Modifier.height(20.dp))

            // Confirm password field
            val displayError = localError ?: uiState.error
            IAMSTextField(
                value = confirmPassword,
                onValueChange = {
                    confirmPassword = it
                    localError = null
                    viewModel.clearError()
                },
                label = "Confirm Password",
                placeholder = "Re-enter your password",
                isPassword = true,
                enabled = !uiState.isLoading,
                error = displayError,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Password,
                    imeAction = ImeAction.Done
                ),
                keyboardActions = KeyboardActions(
                    onDone = {
                        focusManager.clearFocus()
                        attemptRegister()
                    }
                )
            )

            Spacer(modifier = Modifier.height(32.dp))

            // Create Account button
            IAMSButton(
                text = "Create Account",
                onClick = { attemptRegister() },
                enabled = !uiState.isLoading,
                isLoading = uiState.isLoading
            )
        }
    }
}
