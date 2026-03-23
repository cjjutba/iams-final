package com.iams.app.ui.auth

import androidx.compose.foundation.border
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MarkEmailRead
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.AuthLayout
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

@Composable
fun EmailVerificationScreen(
    navController: NavController,
    email: String,
    viewModel: RegistrationViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val toastState = LocalToastState.current

    // Toast on resend success
    LaunchedEffect(uiState.resendSuccess) {
        if (uiState.resendSuccess) {
            toastState.showToast("Verification email sent!", ToastType.SUCCESS)
            viewModel.clearResendSuccess()
        }
    }

    // Toast on error
    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            toastState.showToast(it, ToastType.ERROR)
            viewModel.clearError()
        }
    }

    // Start auto-polling for email verification
    LaunchedEffect(email) {
        viewModel.startEmailPolling(email)
    }

    // Stop polling when leaving screen
    DisposableEffect(Unit) {
        onDispose { viewModel.stopEmailPolling() }
    }

    // Toast + navigate on verified → go to student login
    LaunchedEffect(uiState.emailVerified) {
        if (uiState.emailVerified) {
            toastState.showToast("Email verified! You can now sign in.", ToastType.SUCCESS)
            navController.navigate(Routes.STUDENT_LOGIN) {
                popUpTo(0) { inclusive = true }
            }
        }
    }

    AuthLayout(
        showBack = true,
        title = "Verify Your Email",
        subtitle = "We sent a verification link to your email",
        onBack = {
            navController.navigate(Routes.LOGIN) {
                popUpTo(Routes.REGISTER_STEP1) { inclusive = true }
            }
        }
    ) {
        Spacer(modifier = Modifier.height(24.dp))

        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Mail icon in circle
            Box(
                modifier = Modifier
                    .size(80.dp)
                    .border(2.dp, Border, CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.MarkEmailRead,
                    contentDescription = "Email sent",
                    modifier = Modifier.size(40.dp),
                    tint = Primary
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Description text
            Text(
                text = "We sent a verification email to:",
                style = MaterialTheme.typography.bodyLarge,
                color = TextSecondary,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(8.dp))

            // Email address badge
            Text(
                text = email,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                color = Primary,
                textAlign = TextAlign.Center,
                modifier = Modifier
                    .background(Secondary, RoundedCornerShape(10.dp))
                    .padding(horizontal = 16.dp, vertical = 8.dp)
            )

            Spacer(modifier = Modifier.height(20.dp))

            // Instructions
            Text(
                text = "Click the link in the email to verify your account. Once verified, you can sign in to IAMS.",
                style = MaterialTheme.typography.bodyLarge,
                color = TextSecondary,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(8.dp))

            // Hint
            Text(
                text = "If you do not see the email, check your spam or junk folder.",
                style = MaterialTheme.typography.bodySmall,
                color = TextTertiary,
                textAlign = TextAlign.Center
            )

            // Polling indicator
            if (uiState.isPolling) {
                Spacer(modifier = Modifier.height(24.dp))

                CircularProgressIndicator(
                    modifier = Modifier.size(24.dp),
                    color = Primary,
                    strokeWidth = 2.dp
                )

                Spacer(modifier = Modifier.height(8.dp))

                Text(
                    text = "Checking automatically...",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Check Verification Status button (primary)
            IAMSButton(
                text = "Check Verification Status",
                onClick = { viewModel.checkEmailVerified(email) },
                enabled = !uiState.isLoading,
                isLoading = uiState.isLoading,
                size = IAMSButtonSize.LG
            )

            Spacer(modifier = Modifier.height(12.dp))

            // Resend Verification Email button (outline)
            IAMSButton(
                text = "Resend Verification Email",
                onClick = { viewModel.resendVerificationEmail(email) },
                variant = IAMSButtonVariant.OUTLINE,
                size = IAMSButtonSize.LG
            )

            Spacer(modifier = Modifier.height(12.dp))

            // Back to Login button (ghost)
            IAMSButton(
                text = "Back to Login",
                onClick = {
                    navController.navigate(Routes.LOGIN) {
                        popUpTo(Routes.REGISTER_STEP1) { inclusive = true }
                    }
                },
                variant = IAMSButtonVariant.GHOST,
                size = IAMSButtonSize.MD
            )
        }
    }
}
