package com.iams.app.ui.auth

import android.Manifest
import android.graphics.Bitmap
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.content.PermissionChecker
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.AuthLayout
import com.iams.app.ui.components.FaceCaptureView
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextSecondary

private const val MIN_CAPTURES = 3
private const val MAX_CAPTURES = 5

private val GUIDANCE_PROMPTS = listOf(
    "Look straight at the camera",
    "Turn your head slightly to the left",
    "Turn your head slightly to the right",
    "Tilt your head slightly up",
    "Tilt your head slightly down"
)

@Composable
fun RegisterStep3Screen(
    navController: NavController,
    viewModel: RegistrationViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val toastState = LocalToastState.current
    val context = LocalContext.current
    var cameraPermissionGranted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                    PermissionChecker.PERMISSION_GRANTED
        )
    }
    var permissionDenied by remember { mutableStateOf(false) }
    var captureIndex by remember { mutableIntStateOf(0) }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        cameraPermissionGranted = isGranted
        if (!isGranted) {
            permissionDenied = true
        }
    }

    val capturedCount = uiState.capturedFaces.size
    val currentGuidance = if (captureIndex < GUIDANCE_PROMPTS.size) {
        GUIDANCE_PROMPTS[captureIndex]
    } else {
        "Capture another angle"
    }

    AuthLayout(
        showBack = true,
        title = "Create Account",
        subtitle = "Step 3 of 4 - Register your face",
        onBack = { navController.popBackStack() }
    ) {
        Spacer(modifier = Modifier.height(8.dp))

        // Progress indicator
        Text(
            text = "Step 3 of 4",
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary
        )

        Spacer(modifier = Modifier.height(8.dp))

        LinearProgressIndicator(
            progress = { 0.75f },
            modifier = Modifier
                .fillMaxWidth()
                .height(6.dp)
                .clip(RoundedCornerShape(50)),
            color = Primary,
            trackColor = Border,
        )

        Spacer(modifier = Modifier.height(20.dp))

        Spacer(modifier = Modifier.height(16.dp))

        // Title
        Text(
            text = "Face Registration",
            style = MaterialTheme.typography.headlineLarge,
            color = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(modifier = Modifier.height(12.dp))

        // Capture count
        Text(
            text = "$capturedCount / $MAX_CAPTURES captured (min $MIN_CAPTURES)",
            style = MaterialTheme.typography.bodyLarge,
            color = if (capturedCount >= MIN_CAPTURES) PresentFg else TextSecondary,
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(modifier = Modifier.height(24.dp))

        // Camera / permission content
        when {
            // Camera permission granted and still capturing
            cameraPermissionGranted && capturedCount < MAX_CAPTURES -> {
                FaceCaptureView(
                    guidanceText = currentGuidance,
                    onCapture = { bitmap ->
                        viewModel.addCapturedFace(bitmap)
                        captureIndex = capturedCount + 1
                        toastState.showToast("Photo ${capturedCount + 1} captured", ToastType.INFO)
                    },
                    modifier = Modifier.fillMaxWidth()
                )
            }

            // Max captures reached
            cameraPermissionGranted && capturedCount >= MAX_CAPTURES -> {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(200.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            Icons.Default.CheckCircle,
                            contentDescription = "Complete",
                            modifier = Modifier.size(64.dp),
                            tint = PresentFg
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = "All $MAX_CAPTURES photos captured!",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = PresentFg
                        )
                    }
                }
            }

            // Permission not granted yet
            !cameraPermissionGranted && !permissionDenied -> {
                PermissionRequestContent(
                    onRequestPermission = {
                        permissionLauncher.launch(Manifest.permission.CAMERA)
                    }
                )
            }

            // Permission denied
            permissionDenied -> {
                PermissionDeniedContent()
            }
        }

        // Captured faces preview
        if (capturedCount > 0) {
            Spacer(modifier = Modifier.height(24.dp))

            Text(
                text = "Captured Photos",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.SemiBold,
                color = TextSecondary,
                modifier = Modifier.fillMaxWidth()
            )

            Spacer(modifier = Modifier.height(12.dp))

            LazyRow(
                contentPadding = PaddingValues(horizontal = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                itemsIndexed(uiState.capturedFaces) { index, bitmap ->
                    CapturedFaceThumbnail(
                        bitmap = bitmap,
                        index = index,
                        onRemove = {
                            viewModel.removeCapturedFace(index)
                            captureIndex = uiState.capturedFaces.size - 1
                        }
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(32.dp))

        // Done button (visible when min captures reached)
        if (capturedCount >= MIN_CAPTURES) {
            IAMSButton(
                text = "Continue to Review",
                onClick = {
                    navController.navigate(Routes.REGISTER_REVIEW_INNER)
                }
            )

            Spacer(modifier = Modifier.height(12.dp))
        }

        // Skip button
        IAMSButton(
            text = "Skip for Now",
            onClick = {
                viewModel.clearCapturedFaces()
                navController.navigate(Routes.REGISTER_REVIEW_INNER)
            },
            variant = IAMSButtonVariant.OUTLINE
        )
    }
}

@Composable
private fun CapturedFaceThumbnail(
    bitmap: Bitmap,
    index: Int,
    onRemove: () -> Unit
) {
    Box(modifier = Modifier.size(80.dp)) {
        Image(
            bitmap = bitmap.asImageBitmap(),
            contentDescription = "Captured face ${index + 1}",
            modifier = Modifier
                .fillMaxSize()
                .clip(RoundedCornerShape(10.dp))
                .border(1.dp, Border, RoundedCornerShape(10.dp))
        )
        IconButton(
            onClick = onRemove,
            modifier = Modifier
                .size(24.dp)
                .align(Alignment.TopEnd)
        ) {
            Icon(
                Icons.Default.Close,
                contentDescription = "Remove",
                modifier = Modifier.size(16.dp),
                tint = MaterialTheme.colorScheme.error
            )
        }
    }
}

@Composable
private fun PermissionRequestContent(onRequestPermission: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            imageVector = Icons.Default.CameraAlt,
            contentDescription = "Camera",
            modifier = Modifier.size(80.dp),
            tint = TextSecondary
        )

        Spacer(modifier = Modifier.height(24.dp))

        Text(
            text = "Camera Permission Required",
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.onBackground
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "We need access to your camera to capture face photos for attendance recognition.",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(24.dp))

        IAMSButton(
            text = "Grant Camera Permission",
            onClick = onRequestPermission
        )
    }
}

@Composable
private fun PermissionDeniedContent() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            imageVector = Icons.Default.CameraAlt,
            contentDescription = "Camera",
            modifier = Modifier.size(80.dp),
            tint = MaterialTheme.colorScheme.error
        )

        Spacer(modifier = Modifier.height(24.dp))

        Text(
            text = "Camera Permission Denied",
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.error
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Camera access was denied. You can skip face registration for now and register your face later from your profile settings.",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = TextAlign.Center
        )
    }
}
