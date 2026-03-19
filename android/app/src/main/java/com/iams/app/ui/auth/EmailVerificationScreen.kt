package com.iams.app.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
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
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary

@Composable
fun EmailVerificationScreen(
    navController: NavController,
    email: String,
    viewModel: RegistrationViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    // Start auto-polling for email verification
    LaunchedEffect(email) {
        viewModel.startEmailPolling(email)
    }

    // Stop polling when leaving screen
    DisposableEffect(Unit) {
        onDispose { viewModel.stopEmailPolling() }
    }

    // Navigate on verified
    LaunchedEffect(uiState.emailVerified) {
        if (uiState.emailVerified) {
            navController.navigate(Routes.REGISTER_STEP3) {
                popUpTo(Routes.REGISTER_STEP1) { inclusive = true }
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        // Header
        IAMSHeader(
            title = "Verify Email",
            onBack = {
                navController.navigate(Routes.LOGIN) {
                    popUpTo(Routes.REGISTER_STEP1) { inclusive = true }
                }
            }
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp)
                .padding(top = 48.dp, bottom = 32.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Email icon
            Icon(
                imageVector = Icons.Default.MarkEmailRead,
                contentDescription = "Email sent",
                modifier = Modifier.size(80.dp),
                tint = Primary
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Title
            Text(
                text = "Verify Your Email",
                style = MaterialTheme.typography.headlineLarge,
                color = MaterialTheme.colorScheme.onBackground,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(16.dp))

            // Subtitle
            Text(
                text = "We've sent a verification link to:",
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

            Spacer(modifier = Modifier.height(24.dp))

            // Instructions
            Text(
                text = "Please check your inbox and click the verification link to continue.",
                style = MaterialTheme.typography.bodyLarge,
                color = TextSecondary,
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

            // Error message
            if (uiState.error != null) {
                Spacer(modifier = Modifier.height(12.dp))

                Text(
                    text = uiState.error!!,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                    textAlign = TextAlign.Center
                )
            }

            Spacer(modifier = Modifier.height(32.dp))

            // Verify button
            IAMSButton(
                text = "I've Verified My Email",
                onClick = { viewModel.checkEmailVerified(email) },
                enabled = !uiState.isLoading,
                isLoading = uiState.isLoading
            )

            Spacer(modifier = Modifier.height(12.dp))

            // Back to login
            IAMSButton(
                text = "Back to Login",
                onClick = {
                    navController.navigate(Routes.LOGIN) {
                        popUpTo(Routes.REGISTER_STEP1) { inclusive = true }
                    }
                },
                variant = IAMSButtonVariant.OUTLINE
            )
        }
    }
}
