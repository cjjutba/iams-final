package com.iams.app.ui.auth

import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
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
import com.iams.app.ui.components.AuthLayout
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSTextField
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
import com.iams.app.ui.navigation.Routes
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

    AuthLayout(
        showBack = true,
        title = "Create Account",
        subtitle = "Step 1 of 4 - Verify your identity",
        onBack = { navController.popBackStack() }
    ) {
        // Progress section
        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Step 1 of 4",
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary
        )

        Spacer(modifier = Modifier.height(8.dp))

        LinearProgressIndicator(
            progress = { 0.25f },
            modifier = Modifier
                .fillMaxWidth()
                .height(6.dp)
                .clip(RoundedCornerShape(50)),
            color = Primary,
            trackColor = Border,
        )

        Spacer(modifier = Modifier.height(20.dp))

        // Section start
        Spacer(modifier = Modifier.height(16.dp))

        // Helper text
        Text(
            text = "Enter your student ID and birthdate to verify your enrollment.",
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary
        )

        Spacer(modifier = Modifier.height(20.dp))

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
            error = null,
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
