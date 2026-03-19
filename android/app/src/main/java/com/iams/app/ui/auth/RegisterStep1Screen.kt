package com.iams.app.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.platform.LocalFocusManager
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
import com.iams.app.ui.theme.TextSecondary

@Composable
fun RegisterStep1Screen(
    navController: NavController,
    viewModel: RegistrationViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    var studentId by remember { mutableStateOf("") }
    var birthdate by remember { mutableStateOf("") }
    val focusManager = LocalFocusManager.current

    // Navigate on successful verification
    LaunchedEffect(uiState.studentVerified) {
        if (uiState.studentVerified) {
            navController.navigate(
                Routes.registerStep2(
                    studentId = uiState.studentId,
                    firstName = uiState.firstName,
                    lastName = uiState.lastName
                )
            )
            viewModel.resetVerification()
        }
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
                progress = { 0.33f },
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
                text = "Step 1 of 3",
                style = MaterialTheme.typography.bodySmall,
                color = Primary
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Title
            Text(
                text = "Student Verification",
                style = MaterialTheme.typography.headlineLarge,
                color = MaterialTheme.colorScheme.onBackground
            )

            Spacer(modifier = Modifier.height(12.dp))

            // Subtitle
            Text(
                text = "Enter your student ID and birthdate to verify your enrollment.",
                style = MaterialTheme.typography.bodyLarge,
                color = TextSecondary
            )

            Spacer(modifier = Modifier.height(32.dp))

            // Student ID field
            IAMSTextField(
                value = studentId,
                onValueChange = {
                    studentId = it
                    viewModel.clearError()
                },
                label = "Student ID",
                placeholder = "e.g., 2021-00123",
                enabled = !uiState.isLoading,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Text,
                    imeAction = ImeAction.Next
                ),
                keyboardActions = KeyboardActions(
                    onNext = { focusManager.moveFocus(FocusDirection.Down) }
                )
            )

            Spacer(modifier = Modifier.height(20.dp))

            // Birthdate field
            IAMSTextField(
                value = birthdate,
                onValueChange = {
                    birthdate = it
                    viewModel.clearError()
                },
                label = "Birthdate",
                placeholder = "YYYY-MM-DD",
                enabled = !uiState.isLoading,
                error = uiState.error,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Number,
                    imeAction = ImeAction.Done
                ),
                keyboardActions = KeyboardActions(
                    onDone = {
                        focusManager.clearFocus()
                        viewModel.verifyStudentId(studentId, birthdate)
                    }
                )
            )

            Spacer(modifier = Modifier.height(32.dp))

            // Verify button
            IAMSButton(
                text = "Verify",
                onClick = { viewModel.verifyStudentId(studentId, birthdate) },
                enabled = !uiState.isLoading,
                isLoading = uiState.isLoading
            )
        }
    }
}
