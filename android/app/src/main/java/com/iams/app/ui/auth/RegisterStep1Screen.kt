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
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
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
import com.iams.app.ui.utils.InputSanitizer
import com.iams.app.ui.utils.InputValidation
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
    var studentIdError by remember { mutableStateOf<String?>(null) }
    var birthdateError by remember { mutableStateOf<String?>(null) }
    val focusManager = LocalFocusManager.current
    val toastState = LocalToastState.current

    // Toast on error
    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            toastState.showToast(it, ToastType.ERROR)
            viewModel.clearError()
        }
    }

    // Toast + navigate on successful verification
    LaunchedEffect(uiState.studentVerified) {
        if (uiState.studentVerified) {
            toastState.showToast("Student ID verified", ToastType.SUCCESS)
            navController.navigate(
                Routes.registerStep2(
                    studentId = uiState.studentId,
                    firstName = uiState.firstName,
                    lastName = uiState.lastName,
                    email = uiState.email
                )
            )
            viewModel.resetVerification()
        }
    }

    AuthLayout(
        showBack = true,
        title = "Create Account",
        subtitle = "Step 1 of 4 - Verify your identity",
        onBack = {
            if (uiState.studentIdChecked) {
                viewModel.resetStudentIdCheck()
                birthdate = ""
            } else {
                navController.popBackStack()
            }
        }
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

        // Helper text changes based on phase
        Text(
            text = if (uiState.studentIdChecked)
                "Enter your birthdate to verify your identity."
            else
                "Enter your student ID to verify your enrollment.",
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary
        )

        Spacer(modifier = Modifier.height(20.dp))

        // Student ID field (always visible, disabled in phase 2)
        IAMSTextField(
            value = studentId,
            onValueChange = {
                studentId = it
                studentIdError = null
                viewModel.clearError()
            },
            label = "Student ID",
            placeholder = "e.g., 21-A-01234",
            error = studentIdError,
            enabled = !uiState.isLoading && !uiState.studentIdChecked,
            keyboardOptions = KeyboardOptions(
                capitalization = KeyboardCapitalization.Characters,
                keyboardType = KeyboardType.Text,
                imeAction = if (uiState.studentIdChecked) ImeAction.Next else ImeAction.Done
            ),
            keyboardActions = KeyboardActions(
                onDone = {
                    if (!uiState.studentIdChecked) {
                        focusManager.clearFocus()
                        viewModel.checkStudentId(studentId)
                    }
                }
            )
        )

        // Phase 2: Birthdate field (shown after student ID is checked)
        if (uiState.studentIdChecked) {
            Spacer(modifier = Modifier.height(20.dp))

            IAMSTextField(
                value = birthdate,
                onValueChange = { newValue ->
                    birthdate = InputSanitizer.digitsOnly(newValue, 8)
                    birthdateError = null
                    viewModel.clearError()
                },
                label = "Birthdate",
                placeholder = "e.g., 01132003",
                error = birthdateError,
                supportingText = "Format: MMDDYYYY",
                enabled = !uiState.isLoading,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Number,
                    imeAction = ImeAction.Done
                ),
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
            )
        }

        Spacer(modifier = Modifier.height(32.dp))

        if (uiState.studentIdChecked) {
            // Phase 2: Verify button
            IAMSButton(
                text = "Verify",
                onClick = {
                    val err = InputValidation.validateBirthdate(birthdate)
                    birthdateError = err
                    if (err != null) return@IAMSButton
                    val formatted = formatBirthdateForApi(birthdate)
                    viewModel.verifyStudentId(studentId, formatted)
                },
                enabled = !uiState.isLoading,
                isLoading = uiState.isLoading,
                loadingText = "Verifying..."
            )
        } else {
            // Phase 1: Continue button
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
        }
    }
}

/**
 * Convert MMDDYYYY to YYYY-MM-DD for the backend API.
 */
private fun formatBirthdateForApi(mmddyyyy: String): String {
    val mm = mmddyyyy.substring(0, 2)
    val dd = mmddyyyy.substring(2, 4)
    val yyyy = mmddyyyy.substring(4, 8)
    return "$yyyy-$mm-$dd"
}
