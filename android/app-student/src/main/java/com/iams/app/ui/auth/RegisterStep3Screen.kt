package com.iams.app.ui.auth

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Icon
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
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.content.PermissionChecker
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.FaceScanScreen
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextSecondary

private enum class Phase { INTRO, SCANNING }

@Composable
fun RegisterStep3Screen(
    navController: NavController,
    viewModel: RegistrationViewModel = hiltViewModel(),
    isStandalone: Boolean = false,
    isReregister: Boolean = false
) {
    val context = LocalContext.current
    var phase by remember { mutableStateOf(Phase.INTRO) }
    var cameraPermissionGranted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                    PermissionChecker.PERMISSION_GRANTED
        )
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        cameraPermissionGranted = isGranted
        if (isGranted) {
            phase = Phase.SCANNING
        }
    }

    val uiState by viewModel.uiState.collectAsState()
    val toastState = com.iams.app.ui.components.LocalToastState.current

    // Handle upload success in standalone mode
    LaunchedEffect(uiState.uploadSuccess) {
        if (uiState.uploadSuccess && isStandalone) {
            toastState.showToast("Face registered successfully!", com.iams.app.ui.components.ToastType.SUCCESS)
            navController.popBackStack()
        }
    }

    // Handle upload error in standalone mode
    LaunchedEffect(uiState.uploadError) {
        if (isStandalone) {
            uiState.uploadError?.let {
                toastState.showToast(it, com.iams.app.ui.components.ToastType.ERROR)
                viewModel.clearUploadError()
            }
        }
    }

    when (phase) {
        // ═══════════════════════════════════════════════════════════
        // INTRO — face enrollment landing screen. No skip affordance:
        // attendance recognition only works when every student has a
        // FAISS embedding on file, so enrollment is mandatory here.
        // ═══════════════════════════════════════════════════════════
        Phase.INTRO -> {
            FaceRegistrationIntro(
                onBack = { navController.popBackStack() },
                onGetStarted = {
                    if (cameraPermissionGranted) {
                        phase = Phase.SCANNING
                    } else {
                        permissionLauncher.launch(Manifest.permission.CAMERA)
                    }
                },
            )
        }

        // ═══════════════════════════════════════════════════════════
        // SCANNING — Full-screen face scan camera (RN FaceScanCamera)
        // ═══════════════════════════════════════════════════════════
        Phase.SCANNING -> {
            FaceScanScreen(
                onComplete = { bitmaps ->
                    viewModel.clearCapturedFaces()
                    bitmaps.forEach { viewModel.addCapturedFace(it) }
                    if (isStandalone) {
                        // Already authenticated — upload immediately
                        viewModel.uploadFaceImages(reregister = isReregister)
                    } else {
                        // During signup — go to review screen
                        navController.navigate(Routes.REGISTER_REVIEW_INNER)
                    }
                },
                onCancel = {
                    phase = Phase.INTRO
                },
                isUploading = uiState.isUploading
            )
        }
    }
}

// ── Intro Screen ─────────────────────────────────────────────────
// Landing phase for face enrollment. Students must proceed via "Get
// started" — no skip path is offered because classroom attendance
// recognition requires a registered embedding.

@Composable
private fun FaceRegistrationIntro(
    onBack: () -> Unit,
    onGetStarted: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 24.dp)
            .padding(top = 16.dp, bottom = 32.dp)
    ) {
        // Back button
        Row(
            modifier = Modifier
                .clickable(
                    interactionSource = remember { MutableInteractionSource() },
                    indication = null,
                    onClick = onBack
                )
                .padding(vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.AutoMirrored.Filled.ArrowBack,
                contentDescription = "Back",
                modifier = Modifier.size(24.dp),
                tint = Primary
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = "Back",
                style = MaterialTheme.typography.bodyLarge,
                color = Primary
            )
        }

        // Center content
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            // Face illustration — frame corners with minimal face features
            Box(
                modifier = Modifier
                    .size(width = 170.dp, height = 220.dp)
                    .drawBehind {
                        val cornerLen = 24.dp.toPx()
                        val strokeW = 2.5.dp.toPx()
                        val w = size.width
                        val h = size.height
                        val color = Color.Black

                        // Top-left corner
                        drawLine(color, Offset(0f, cornerLen), Offset(0f, 0f), strokeW)
                        drawLine(color, Offset(0f, 0f), Offset(cornerLen, 0f), strokeW)
                        // Top-right corner
                        drawLine(color, Offset(w - cornerLen, 0f), Offset(w, 0f), strokeW)
                        drawLine(color, Offset(w, 0f), Offset(w, cornerLen), strokeW)
                        // Bottom-left corner
                        drawLine(color, Offset(0f, h - cornerLen), Offset(0f, h), strokeW)
                        drawLine(color, Offset(0f, h), Offset(cornerLen, h), strokeW)
                        // Bottom-right corner
                        drawLine(color, Offset(w - cornerLen, h), Offset(w, h), strokeW)
                        drawLine(color, Offset(w, h - cornerLen), Offset(w, h), strokeW)

                        // Face features
                        val eyeWidth = 16.dp.toPx()
                        val eyeHeight = 2.5.dp.toPx()
                        val eyeGap = 34.dp.toPx()
                        val mouthWidth = 22.dp.toPx()
                        val centerX = w / 2f
                        val centerY = h / 2f

                        // Left eye dash
                        drawRoundRect(
                            color = color,
                            topLeft = Offset(centerX - eyeGap / 2f - eyeWidth, centerY - 15.dp.toPx()),
                            size = Size(eyeWidth, eyeHeight),
                            cornerRadius = CornerRadius(2.dp.toPx())
                        )
                        // Right eye dash
                        drawRoundRect(
                            color = color,
                            topLeft = Offset(centerX + eyeGap / 2f, centerY - 15.dp.toPx()),
                            size = Size(eyeWidth, eyeHeight),
                            cornerRadius = CornerRadius(2.dp.toPx())
                        )
                        // Mouth dash
                        drawRoundRect(
                            color = color,
                            topLeft = Offset(centerX - mouthWidth / 2f, centerY + 15.dp.toPx()),
                            size = Size(mouthWidth, eyeHeight),
                            cornerRadius = CornerRadius(2.dp.toPx())
                        )
                    },
                contentAlignment = Alignment.Center
            ) {}

            Spacer(modifier = Modifier.height(36.dp))

            Text(
                text = "Register your face",
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onBackground
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = "We'll use your face so classroom cameras can recognize you and mark your attendance automatically",
                style = MaterialTheme.typography.bodyLarge,
                textAlign = TextAlign.Center,
                color = TextSecondary
            )
        }

        // Bottom button — face enrollment is required to continue.
        IAMSButton(
            text = "Get started",
            onClick = onGetStarted,
            modifier = Modifier.fillMaxWidth()
        )
    }
}
