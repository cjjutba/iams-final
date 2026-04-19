package com.iams.app.ui.auth

import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLinkStyles
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withLink
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.AuthLayout
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.LegalDocument
import com.iams.app.ui.components.LegalDocumentSheet
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastState
import com.iams.app.ui.components.ToastType
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.LinkBlue
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

/**
 * Step 4 (Review): Shows collected data, creates the account, and uploads face images.
 *
 * Flow: register() → save tokens → uploadFaceImages() → navigate to login.
 * If face upload fails, shows a retry button. Face images are uploaded
 * immediately using the tokens returned by the registration endpoint.
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
    var activeLegalDoc by remember { mutableStateOf<LegalDocument?>(null) }

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

    // After account creation → upload faces immediately using registration tokens
    LaunchedEffect(uiState.accountCreated) {
        if (uiState.accountCreated) {
            if (hasFaces) {
                // Upload face images right away — tokens are already saved
                viewModel.uploadFaceImages()
            } else {
                // No faces captured — skip upload, go to login
                navigateToLogin(viewModel, navController, toastState)
            }
        }
    }

    // After face upload succeeds → navigate to login
    LaunchedEffect(uiState.uploadSuccess) {
        if (uiState.uploadSuccess && uiState.accountCreated) {
            navigateToLogin(viewModel, navController, toastState)
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
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.Top
        ) {
            Icon(
                imageVector = if (isAgreed) Icons.Filled.CheckBox else Icons.Filled.CheckBoxOutlineBlank,
                contentDescription = if (isAgreed) "Agreed" else "Not agreed",
                modifier = Modifier
                    .size(22.dp)
                    .clickable(
                        interactionSource = remember { MutableInteractionSource() },
                        indication = null,
                        onClick = { isAgreed = !isAgreed }
                    ),
                tint = if (isAgreed) Primary else TextTertiary
            )
            Spacer(modifier = Modifier.width(12.dp))

            val linkStyles = TextLinkStyles(
                style = SpanStyle(color = LinkBlue, fontWeight = FontWeight.Medium)
            )
            val agreementText = buildAnnotatedString {
                append("I agree to the ")
                withLink(
                    LinkAnnotation.Clickable(
                        tag = "terms",
                        styles = linkStyles,
                        linkInteractionListener = {
                            activeLegalDoc = LegalDocument.TERMS_OF_SERVICE
                        }
                    )
                ) { append("Terms of Service") }
                append(" and ")
                withLink(
                    LinkAnnotation.Clickable(
                        tag = "privacy",
                        styles = linkStyles,
                        linkInteractionListener = {
                            activeLegalDoc = LegalDocument.PRIVACY_POLICY
                        }
                    )
                ) { append("Privacy Policy") }
            }
            Text(
                text = agreementText,
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }

        // ── Terms / Privacy slide-up sheet ────────────────
        activeLegalDoc?.let { doc ->
            LegalDocumentSheet(
                document = doc,
                onDismiss = { activeLegalDoc = null }
            )
        }

        Spacer(modifier = Modifier.height(32.dp))

        if (uiState.isUploading) {
            // ── Face Upload Progress ─────────────────────────
            Column(
                modifier = Modifier.fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                LinearProgressIndicator(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(6.dp)
                        .clip(RoundedCornerShape(50)),
                    color = Primary,
                    trackColor = Border,
                )
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    text = "Uploading face data...",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
            }
        } else if (uiState.uploadError != null && uiState.accountCreated) {
            // ── Face Upload Failed — Retry ───────────────────
            Column(
                modifier = Modifier.fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "Face upload failed. Your account was created, but face registration needs to be completed.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                    textAlign = TextAlign.Center
                )
                Spacer(modifier = Modifier.height(16.dp))
                IAMSButton(
                    text = "Retry Face Upload",
                    onClick = {
                        viewModel.clearUploadError()
                        viewModel.uploadFaceImages()
                    },
                    enabled = true,
                    isLoading = false
                )
                Spacer(modifier = Modifier.height(8.dp))
                IAMSButton(
                    text = "Skip for Now",
                    onClick = {
                        // Save faces locally as fallback, then navigate
                        viewModel.savePendingFaceImages()
                        navigateToLogin(viewModel, navController, toastState,
                            message = "Account created! Please register your face from your profile.")
                    },
                    enabled = true,
                    isLoading = false
                )
            }
        } else {
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
                        birthdate = regData.birthdate
                    )
                },
                enabled = !uiState.isLoading && isAgreed && !uiState.accountCreated,
                isLoading = uiState.isLoading,
                loadingText = "Creating Account..."
            )
        }
    }
}

private fun navigateToLogin(
    viewModel: RegistrationViewModel,
    navController: NavController,
    toastState: ToastState,
    message: String = "Account created! You can now sign in."
) {
    toastState.showToast(message, ToastType.SUCCESS)
    RegistrationDataHolder.clear()
    viewModel.resetRegistration()
    navController.navigate(Routes.STUDENT_LOGIN) {
        popUpTo(Routes.WELCOME) { inclusive = false }
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
