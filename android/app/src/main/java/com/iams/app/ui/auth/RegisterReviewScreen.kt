package com.iams.app.ui.auth

import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckBox
import androidx.compose.material.icons.filled.CheckBoxOutlineBlank
import androidx.compose.material.icons.filled.CheckCircle
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.AuthLayout
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

/**
 * Step 4 (Review): Shows collected data and creates the account.
 *
 * This is where register() is called (creates Supabase Auth user + sends verification email).
 * Face images are saved locally as "pending" and uploaded after the user logs in.
 * Matches the React Native flow in RegisterReviewScreen.tsx.
 */
@Composable
fun RegisterReviewScreen(
    navController: NavController,
    viewModel: RegistrationViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val toastState = LocalToastState.current
    val hasFaces = uiState.capturedFaces.isNotEmpty()
    var isAgreed by remember { mutableStateOf(false) }

    // Read registration data from holder (set in Step 2)
    val regData = RegistrationDataHolder
    val email = regData.email
    val studentId = regData.studentId
    val firstName = regData.firstName
    val lastName = regData.lastName

    // Toast on error
    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            toastState.showToast(it, ToastType.ERROR)
            viewModel.clearError()
        }
    }

    // After registration succeeds → save pending face images → navigate to email verification
    LaunchedEffect(uiState.registrationComplete) {
        if (uiState.registrationComplete) {
            // Save face images for later upload (after login, when we have a valid token)
            if (hasFaces) {
                viewModel.savePendingFaceImages()
            }

            toastState.showToast("Account created! Please verify your email.", ToastType.SUCCESS)
            RegistrationDataHolder.clear()
            viewModel.resetRegistration()

            // Navigate to email verification. Don't popUpTo here — the face-flow
            // back stack entry is still referenced by the shared ViewModel.
            // EmailVerificationScreen handles back stack cleanup on completion.
            navController.navigate(Routes.emailVerification(email))
        }
    }

    AuthLayout(
        showBack = true,
        title = "Create Account",
        subtitle = "Step 4 of 4 - Review your information",
        onBack = { navController.popBackStack() }
    ) {
        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Step 4 of 4",
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary
        )

        Spacer(modifier = Modifier.height(8.dp))

        LinearProgressIndicator(
            progress = { 1f },
            modifier = Modifier
                .fillMaxWidth()
                .height(6.dp)
                .clip(RoundedCornerShape(50)),
            color = Primary,
            trackColor = Border,
        )

        Spacer(modifier = Modifier.height(24.dp))

        // ── Student Information ──────────────────────────
        Text(
            text = "Student Information",
            style = MaterialTheme.typography.bodyLarge,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.onBackground
        )

        Spacer(modifier = Modifier.height(16.dp))

        ReviewInfoRow(label = "Student ID", value = studentId)
        Spacer(modifier = Modifier.height(16.dp))
        ReviewInfoRow(label = "Name", value = "$firstName $lastName".trim())
        Spacer(modifier = Modifier.height(16.dp))
        ReviewInfoRow(label = "Email", value = email)

        Spacer(modifier = Modifier.height(24.dp))

        // ── Face Registration ────────────────────────────
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Face Registration",
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onBackground
            )
            if (hasFaces) {
                Icon(
                    Icons.Default.CheckCircle,
                    contentDescription = "Completed",
                    modifier = Modifier.size(22.dp),
                    tint = PresentFg
                )
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = if (hasFaces) {
                "${uiState.capturedFaces.size}/5 photos captured"
            } else {
                "Face registration was skipped. You can register your face later from your profile."
            },
            style = MaterialTheme.typography.bodySmall,
            color = if (hasFaces) PresentFg else TextSecondary
        )

        Spacer(modifier = Modifier.height(24.dp))

        // ── Terms Checkbox ───────────────────────────────
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(
                    interactionSource = remember { MutableInteractionSource() },
                    indication = null,
                    onClick = { isAgreed = !isAgreed }
                ),
            verticalAlignment = Alignment.Top
        ) {
            Icon(
                imageVector = if (isAgreed) Icons.Filled.CheckBox else Icons.Filled.CheckBoxOutlineBlank,
                contentDescription = if (isAgreed) "Agreed" else "Not agreed",
                modifier = Modifier.size(22.dp),
                tint = if (isAgreed) Primary else TextTertiary
            )
            Spacer(modifier = Modifier.width(12.dp))
            Text(
                text = "I agree to the Terms of Service and Privacy Policy",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }

        Spacer(modifier = Modifier.height(32.dp))

        // ── Create Account Button ────────────────────────
        IAMSButton(
            text = "Create Account",
            onClick = {
                viewModel.register(
                    email = email,
                    password = regData.password,
                    studentId = studentId,
                    firstName = firstName,
                    lastName = lastName,
                    birthdate = "2000-01-01"  // Already validated in Step 1
                )
            },
            enabled = !uiState.isLoading && isAgreed,
            isLoading = uiState.isLoading
        )
    }
}

@Composable
private fun ReviewInfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Top
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = TextTertiary
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Medium,
            color = MaterialTheme.colorScheme.onBackground
        )
    }
}
