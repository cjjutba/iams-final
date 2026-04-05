package com.iams.app.ui.components

import android.graphics.Bitmap
import android.graphics.Matrix
import android.util.Log
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathFillType
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import kotlinx.coroutines.delay
import java.util.concurrent.Executors

private const val TOTAL_STEPS = 5
private const val MIN_FACE_SIZE_RATIO = 0.25f

private val STEP_INSTRUCTIONS = listOf(
    "Look straight at the camera",
    "Turn your head slightly left",
    "Turn your head slightly right",
    "Tilt your head slightly up",
    "Tilt your head slightly down"
)

private val STEP_LABELS = listOf("Center", "Left", "Right", "Up", "Down")

private val COLOR_GREEN = Color(0xFF22C55E)
private val COLOR_RETAKE = Color(0xFFF59E0B)

private enum class ScanPhase { SCANNING, COMPLETE, REVIEW }

/**
 * Full-screen face scan camera matching the React Native FaceScanCamera design.
 *
 * Features:
 * - Dark mask with oval cutout
 * - 5-step guided capture (Center, Left, Right, Up, Down)
 * - Angle guide + step indicator dots
 * - Shutter button enabled only when face detected
 * - Review phase with thumbnail grid + retake
 */
@Composable
fun FaceScanScreen(
    onComplete: (List<Bitmap>) -> Unit,
    onCancel: () -> Unit,
    isUploading: Boolean = false,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val configuration = LocalConfiguration.current
    val density = LocalDensity.current

    var phase by remember { mutableStateOf(ScanPhase.SCANNING) }
    var currentStep by remember { mutableIntStateOf(0) }
    var faceDetected by remember { mutableStateOf(false) }
    var retakeIndex by remember { mutableStateOf<Int?>(null) }
    val images = remember { mutableStateListOf<Bitmap>() }
    var showFlash by remember { mutableStateOf(false) }

    val previewView = remember { PreviewView(context) }
    val analysisExecutor = remember { Executors.newSingleThreadExecutor() }
    val faceDetector = remember {
        FaceDetection.getClient(
            FaceDetectorOptions.Builder()
                .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
                .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_ALL)
                .setMinFaceSize(0.15f)
                .build()
        )
    }

    // Flash animation
    val flashAlpha by animateFloatAsState(
        targetValue = if (showFlash) 0.3f else 0f,
        animationSpec = tween(if (showFlash) 50 else 250),
        label = "flash"
    )
    LaunchedEffect(showFlash) {
        if (showFlash) {
            delay(100)
            showFlash = false
        }
    }

    // Completion animation
    var showCompletion by remember { mutableStateOf(false) }
    val completionScale by animateFloatAsState(
        targetValue = if (showCompletion) 1f else 0f,
        animationSpec = spring(dampingRatio = 0.6f, stiffness = 80f),
        label = "completion"
    )

    // Camera setup
    DisposableEffect(Unit) {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(context)
        cameraProviderFuture.addListener({
            val cameraProvider = cameraProviderFuture.get()
            val preview = Preview.Builder().build().also {
                it.surfaceProvider = previewView.surfaceProvider
            }
            val imageAnalysis = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()

            imageAnalysis.setAnalyzer(analysisExecutor) { imageProxy ->
                @androidx.camera.core.ExperimentalGetImage
                val mediaImage = imageProxy.image
                if (mediaImage != null) {
                    val inputImage = InputImage.fromMediaImage(
                        mediaImage, imageProxy.imageInfo.rotationDegrees
                    )
                    faceDetector.process(inputImage)
                        .addOnSuccessListener { faces ->
                            if (faces.isNotEmpty()) {
                                val face = faces[0]
                                val bounds = face.boundingBox
                                val imageWidth = imageProxy.width.toFloat()
                                val faceSizeRatio = bounds.width() / imageWidth
                                val eyesOpen = (face.leftEyeOpenProbability ?: 0f) > 0.15f &&
                                        (face.rightEyeOpenProbability ?: 0f) > 0.15f
                                faceDetected = faceSizeRatio >= MIN_FACE_SIZE_RATIO && eyesOpen
                            } else {
                                faceDetected = false
                            }
                        }
                        .addOnFailureListener {
                            faceDetected = false
                        }
                        .addOnCompleteListener {
                            imageProxy.close()
                        }
                } else {
                    imageProxy.close()
                }
            }

            val cameraSelector = CameraSelector.Builder()
                .requireLensFacing(CameraSelector.LENS_FACING_FRONT)
                .build()

            try {
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(
                    lifecycleOwner,
                    cameraSelector, preview, imageAnalysis
                )
            } catch (e: Exception) {
                Log.e("FaceScanScreen", "Camera bind failed", e)
            }
        }, ContextCompat.getMainExecutor(context))

        onDispose {
            try {
                val cameraProvider = cameraProviderFuture.get()
                cameraProvider.unbindAll()
            } catch (_: Exception) {}
            faceDetector.close()
            analysisExecutor.shutdown()
        }
    }

    // Capture handler
    fun handleCapture() {
        val rawBitmap = previewView.bitmap ?: return
        if (!faceDetected) return
        // Un-mirror the front camera preview bitmap so the backend gets a
        // non-flipped image — ArcFace alignment is NOT mirror-invariant.
        val matrix = Matrix().apply { preScale(-1f, 1f, rawBitmap.width / 2f, rawBitmap.height / 2f) }
        val bitmap = Bitmap.createBitmap(rawBitmap, 0, 0, rawBitmap.width, rawBitmap.height, matrix, true)

        showFlash = true

        if (retakeIndex != null) {
            val idx = retakeIndex!!
            if (idx in images.indices) {
                images[idx] = bitmap
            }
            retakeIndex = null
            faceDetected = false
            phase = ScanPhase.REVIEW
        } else {
            images.add(bitmap)
            if (images.size >= TOTAL_STEPS) {
                showCompletion = true
                phase = ScanPhase.COMPLETE
            } else {
                currentStep = images.size
            }
        }
    }

    // Transition from complete to review
    LaunchedEffect(phase) {
        if (phase == ScanPhase.COMPLETE) {
            delay(1200)
            phase = ScanPhase.REVIEW
        }
    }

    fun handleRetakePhoto(index: Int) {
        retakeIndex = index
        currentStep = index
        faceDetected = false
        showCompletion = false
        phase = ScanPhase.SCANNING
    }

    fun handleRetakeAll() {
        images.clear()
        retakeIndex = null
        currentStep = 0
        faceDetected = false
        showCompletion = false
        phase = ScanPhase.SCANNING
    }

    fun handleConfirm() {
        onComplete(images.toList())
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
    ) {
        // Camera preview — always mounted
        AndroidView(
            factory = {
                previewView.apply {
                    implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                    scaleType = PreviewView.ScaleType.FILL_CENTER
                }
            },
            modifier = Modifier.fillMaxSize()
        )

        when (phase) {
            ScanPhase.REVIEW -> {
                // ═══════════════════════════════════════════
                // REVIEW PHASE — opaque overlay with thumbnails
                // ═══════════════════════════════════════════
                ReviewOverlay(
                    images = images,
                    onRetakePhoto = ::handleRetakePhoto,
                    onRetakeAll = ::handleRetakeAll,
                    onConfirm = ::handleConfirm,
                    isUploading = isUploading
                )
            }

            else -> {
                // ═══════════════════════════════════════════
                // SCANNING / COMPLETE — camera with overlay
                // ═══════════════════════════════════════════

                // Dark mask with oval cutout
                OvalMaskOverlay(
                    ovalStrokeColor = when {
                        phase == ScanPhase.COMPLETE -> COLOR_GREEN
                        faceDetected -> COLOR_GREEN
                        else -> Color.White.copy(alpha = 0.3f)
                    }
                )

                // UI overlay
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.SpaceBetween
                ) {
                    // Top section — title
                    Column(
                        modifier = Modifier.padding(top = 48.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = "Face Scan",
                            fontSize = 20.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = Color.White,
                            textAlign = TextAlign.Center
                        )
                    }

                    // Spacer to push content below oval
                    Spacer(modifier = Modifier.weight(1f))

                    // Bottom section
                    Column(
                        modifier = Modifier.padding(bottom = 32.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        if (phase == ScanPhase.COMPLETE) {
                            // Completion animation
                            Box(
                                modifier = Modifier
                                    .size(88.dp)
                                    .scale(completionScale)
                                    .clip(CircleShape)
                                    .background(COLOR_GREEN.copy(alpha = 0.85f)),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    Icons.Default.Check,
                                    contentDescription = "Done",
                                    modifier = Modifier.size(48.dp),
                                    tint = Color.White
                                )
                            }

                            Spacer(modifier = Modifier.height(12.dp))

                            Text(
                                text = "All photos captured!",
                                fontSize = 20.sp,
                                fontWeight = FontWeight.Bold,
                                color = COLOR_GREEN,
                                textAlign = TextAlign.Center
                            )
                        } else {
                            // Angle guide
                            AngleGuideComposable(
                                step = currentStep,
                                isAligned = faceDetected
                            )

                            // Instruction text
                            Text(
                                text = STEP_INSTRUCTIONS.getOrElse(currentStep) { "Capture another angle" },
                                fontSize = 16.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = Color.White,
                                textAlign = TextAlign.Center,
                                modifier = Modifier.padding(bottom = 16.dp)
                            )

                            // Step indicator dots
                            StepIndicatorComposable(
                                totalSteps = TOTAL_STEPS,
                                currentStep = currentStep,
                                completedSteps = if (retakeIndex != null) {
                                    (0 until images.size).filter { it != retakeIndex }
                                } else {
                                    (0 until currentStep).toList()
                                },
                                retakeIndex = retakeIndex
                            )

                            // Shutter button
                            Box(
                                modifier = Modifier
                                    .size(72.dp)
                                    .border(
                                        width = 4.dp,
                                        color = if (faceDetected) Color.White else Color.White.copy(
                                            alpha = 0.15f
                                        ),
                                        shape = CircleShape
                                    )
                                    .padding(6.dp)
                                    .clip(CircleShape)
                                    .background(
                                        if (faceDetected) Color.White else Color.White.copy(
                                            alpha = 0.08f
                                        )
                                    )
                                    .clickable(
                                        enabled = faceDetected,
                                        interactionSource = remember { MutableInteractionSource() },
                                        indication = null,
                                        onClick = ::handleCapture
                                    ),
                                contentAlignment = Alignment.Center
                            ) {}

                            Spacer(modifier = Modifier.height(8.dp))

                            if (!faceDetected) {
                                Text(
                                    text = "Position your face in the oval",
                                    fontSize = 12.sp,
                                    color = Color.White.copy(alpha = 0.4f),
                                    textAlign = TextAlign.Center
                                )
                            }
                        }
                    }
                }

                // Flash overlay
                if (flashAlpha > 0f) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(Color.White.copy(alpha = flashAlpha))
                    )
                }
            }
        }
    }
}

// ── Oval Mask Overlay ────────────────────────────────────────────────

@Composable
private fun OvalMaskOverlay(ovalStrokeColor: Color) {
    Canvas(modifier = Modifier.fillMaxSize()) {
        val sw = size.width
        val sh = size.height

        val ovalRx = sw * 0.32f
        val ovalRy = sw * 0.44f
        val ovalCx = sw / 2f
        val ovalCy = sh * 0.35f

        // Dark mask with oval hole
        val maskPath = Path().apply {
            fillType = PathFillType.EvenOdd
            // Outer rectangle
            addRect(Rect(0f, 0f, sw, sh))
            // Inner oval (hole)
            addOval(
                Rect(
                    left = ovalCx - ovalRx,
                    top = ovalCy - ovalRy,
                    right = ovalCx + ovalRx,
                    bottom = ovalCy + ovalRy
                )
            )
        }

        drawPath(maskPath, Color.Black.copy(alpha = 0.75f))

        // Oval border
        drawOval(
            color = ovalStrokeColor,
            topLeft = Offset(ovalCx - ovalRx, ovalCy - ovalRy),
            size = Size(ovalRx * 2, ovalRy * 2),
            style = Stroke(width = 3.dp.toPx())
        )
    }
}

// ── Angle Guide ──────────────────────────────────────────────────────

@Composable
private fun AngleGuideComposable(step: Int, isAligned: Boolean) {
    val color = if (isAligned) COLOR_GREEN else Color.White.copy(alpha = 0.8f)
    val bgColor = if (isAligned) COLOR_GREEN.copy(alpha = 0.15f) else Color.Black.copy(alpha = 0.35f)
    val borderColor = if (isAligned) COLOR_GREEN.copy(alpha = 0.5f) else Color.White.copy(alpha = 0.15f)

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.padding(bottom = 8.dp)
    ) {
        Box(
            modifier = Modifier
                .size(52.dp)
                .clip(CircleShape)
                .background(bgColor)
                .border(1.5.dp, borderColor, CircleShape),
            contentAlignment = Alignment.Center
        ) {
            Canvas(modifier = Modifier.size(40.dp)) {
                drawAngleIcon(step, color)
            }
        }

        Spacer(modifier = Modifier.height(4.dp))

        Text(
            text = STEP_LABELS.getOrElse(step) { "Center" },
            fontSize = 11.sp,
            fontWeight = FontWeight.SemiBold,
            color = color
        )
    }
}

private fun DrawScope.drawAngleIcon(step: Int, color: Color) {
    val cx = size.width / 2f
    val cy = size.height / 2f
    val strokeWidth = 2.5.dp.toPx()

    when (step) {
        0 -> {
            // Center — circle with dot
            drawCircle(color, radius = 10.dp.toPx(), center = Offset(cx, cy), style = Stroke(strokeWidth))
            drawCircle(color, radius = 3.dp.toPx(), center = Offset(cx, cy))
        }
        1 -> {
            // Left arrow
            drawLine(color, Offset(28.dp.toPx(), cy), Offset(12.dp.toPx(), cy), strokeWidth)
            drawLine(color, Offset(12.dp.toPx(), cy), Offset(19.dp.toPx(), 13.dp.toPx()), strokeWidth)
            drawLine(color, Offset(12.dp.toPx(), cy), Offset(19.dp.toPx(), 27.dp.toPx()), strokeWidth)
        }
        2 -> {
            // Right arrow
            drawLine(color, Offset(12.dp.toPx(), cy), Offset(28.dp.toPx(), cy), strokeWidth)
            drawLine(color, Offset(28.dp.toPx(), cy), Offset(21.dp.toPx(), 13.dp.toPx()), strokeWidth)
            drawLine(color, Offset(28.dp.toPx(), cy), Offset(21.dp.toPx(), 27.dp.toPx()), strokeWidth)
        }
        3 -> {
            // Up arrow
            drawLine(color, Offset(cx, 28.dp.toPx()), Offset(cx, 12.dp.toPx()), strokeWidth)
            drawLine(color, Offset(cx, 12.dp.toPx()), Offset(13.dp.toPx(), 19.dp.toPx()), strokeWidth)
            drawLine(color, Offset(cx, 12.dp.toPx()), Offset(27.dp.toPx(), 19.dp.toPx()), strokeWidth)
        }
        4 -> {
            // Down arrow
            drawLine(color, Offset(cx, 12.dp.toPx()), Offset(cx, 28.dp.toPx()), strokeWidth)
            drawLine(color, Offset(cx, 28.dp.toPx()), Offset(13.dp.toPx(), 21.dp.toPx()), strokeWidth)
            drawLine(color, Offset(cx, 28.dp.toPx()), Offset(27.dp.toPx(), 21.dp.toPx()), strokeWidth)
        }
    }
}

// ── Step Indicator ───────────────────────────────────────────────────

@Composable
private fun StepIndicatorComposable(
    totalSteps: Int,
    currentStep: Int,
    completedSteps: List<Int>,
    retakeIndex: Int?
) {
    Row(
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.padding(bottom = 28.dp)
    ) {
        for (i in 0 until totalSteps) {
            val state = when {
                retakeIndex != null && i == retakeIndex -> "retake"
                i in completedSteps -> "complete"
                i == currentStep -> "active"
                else -> "pending"
            }
            StepDot(state = state)
        }
    }
}

@Composable
private fun StepDot(state: String) {
    when (state) {
        "complete" -> {
            Box(
                modifier = Modifier
                    .size(14.dp)
                    .clip(CircleShape)
                    .background(COLOR_GREEN),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    Icons.Default.Check,
                    contentDescription = "Complete",
                    modifier = Modifier.size(10.dp),
                    tint = Color.White
                )
            }
        }
        "active" -> {
            // Pulsing active dot
            val infiniteTransition = rememberInfiniteTransition(label = "pulse")
            val scale by infiniteTransition.animateFloat(
                initialValue = 1f,
                targetValue = 1.25f,
                animationSpec = infiniteRepeatable(
                    animation = tween(800),
                    repeatMode = RepeatMode.Reverse
                ),
                label = "pulseScale"
            )
            Box(
                modifier = Modifier
                    .size(18.dp)
                    .scale(scale)
                    .clip(CircleShape)
                    .background(Color.White)
            )
        }
        "retake" -> {
            Box(
                modifier = Modifier
                    .size(18.dp)
                    .clip(CircleShape)
                    .background(COLOR_RETAKE.copy(alpha = 0.2f))
                    .border(2.dp, COLOR_RETAKE, CircleShape)
            )
        }
        else -> {
            // pending
            Box(
                modifier = Modifier
                    .size(14.dp)
                    .clip(CircleShape)
                    .border(1.5.dp, Color.White.copy(alpha = 0.2f), CircleShape)
            )
        }
    }
}

// ── Review Overlay ───────────────────────────────────────────────────

@Composable
private fun ReviewOverlay(
    images: List<Bitmap>,
    onRetakePhoto: (Int) -> Unit,
    onRetakeAll: () -> Unit,
    onConfirm: () -> Unit,
    isUploading: Boolean = false,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
            .padding(horizontal = 20.dp)
            .padding(top = 48.dp, bottom = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Header
        Text(
            text = "Review Your Photos",
            fontSize = 22.sp,
            fontWeight = FontWeight.Bold,
            color = Color.White,
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(4.dp))

        Text(
            text = "Tap any photo to retake it",
            fontSize = 13.sp,
            color = Color.White.copy(alpha = 0.5f),
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(20.dp))

        // Photo grid: Row of 3 on top, Row of 2 centered on bottom
        Column(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(10.dp, Alignment.CenterVertically),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Top row — first 3 photos (Center, Left, Right)
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                for (i in 0 until minOf(3, images.size)) {
                    ReviewThumbnail(
                        bitmap = images[i],
                        label = STEP_LABELS.getOrElse(i) { "Photo ${i + 1}" },
                        onClick = { if (!isUploading) onRetakePhoto(i) },
                        modifier = Modifier.weight(1f),
                        enabled = !isUploading
                    )
                }
            }

            // Bottom row — last 2 photos (Up, Down), centered
            if (images.size > 3) {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    // Leading spacer to center 2 items in a 3-column layout
                    Spacer(modifier = Modifier.weight(0.5f))
                    for (i in 3 until minOf(5, images.size)) {
                        ReviewThumbnail(
                            bitmap = images[i],
                            label = STEP_LABELS.getOrElse(i) { "Photo ${i + 1}" },
                            onClick = { if (!isUploading) onRetakePhoto(i) },
                            modifier = Modifier.weight(1f),
                            enabled = !isUploading
                        )
                    }
                    Spacer(modifier = Modifier.weight(0.5f))
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Confirm button
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp)
                .clip(RoundedCornerShape(25.dp))
                .background(if (isUploading) COLOR_GREEN.copy(alpha = 0.6f) else COLOR_GREEN)
                .then(
                    if (isUploading) Modifier else Modifier.clickable(onClick = onConfirm)
                ),
            contentAlignment = Alignment.Center
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (isUploading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        color = Color.White,
                        strokeWidth = 2.dp
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Text(
                        text = "Registering face...",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                } else {
                    Icon(
                        Icons.Default.Check,
                        contentDescription = "Confirm",
                        modifier = Modifier.size(20.dp),
                        tint = Color.White
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Looks good",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(10.dp))

        // Retake all (disabled during upload)
        Row(
            modifier = Modifier
                .then(
                    if (isUploading) Modifier else Modifier.clickable(
                        interactionSource = remember { MutableInteractionSource() },
                        indication = null,
                        onClick = onRetakeAll
                    )
                )
                .padding(vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.Default.Refresh,
                contentDescription = "Retake all",
                modifier = Modifier.size(14.dp),
                tint = Color.White.copy(alpha = if (isUploading) 0.2f else 0.5f)
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = "Retake All",
                fontSize = 13.sp,
                color = Color.White.copy(alpha = if (isUploading) 0.2f else 0.5f)
            )
        }
    }
}

@Composable
private fun ReviewThumbnail(
    bitmap: Bitmap,
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    Box(
        modifier = modifier
            .aspectRatio(0.78f)
            .clip(RoundedCornerShape(12.dp))
            .then(if (enabled) Modifier.clickable(onClick = onClick) else Modifier)
    ) {
        Image(
            bitmap = bitmap.asImageBitmap(),
            contentDescription = label,
            modifier = Modifier
                .fillMaxSize()
                .graphicsLayer(scaleX = -1f),
            contentScale = ContentScale.Crop
        )

        // Retake icon
        Box(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(6.dp)
                .size(26.dp)
                .clip(CircleShape)
                .background(Color.Black.copy(alpha = 0.5f)),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                Icons.Default.Refresh,
                contentDescription = "Retake",
                modifier = Modifier.size(14.dp),
                tint = Color.White
            )
        }

        // Label at bottom
        Box(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .background(Color.Black.copy(alpha = 0.55f))
                .padding(vertical = 4.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = label,
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold,
                color = Color.White
            )
        }
    }
}
