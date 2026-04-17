package com.iams.app.ui.faculty

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.aspectRatio
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material.icons.filled.WifiOff
import androidx.compose.material.icons.outlined.Assignment
import androidx.compose.material.icons.outlined.VideocamOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import android.app.Activity
import android.content.pm.ActivityInfo
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.material.icons.filled.Fullscreen
import androidx.compose.material.icons.filled.FullscreenExit
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.IntSize
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.BuildConfig
import com.iams.app.data.model.StudentAttendanceStatus
import com.iams.app.hybrid.HybridMode
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.SkeletonBox
import com.iams.app.ui.components.HybridTrackOverlay
import com.iams.app.ui.components.InterpolatedTrackOverlay
import com.iams.app.ui.components.NativeWebRtcVideoPlayer
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.debug.HybridDiagnosticHud
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.input.pointer.pointerInput
import com.iams.app.ui.theme.AbsentBg
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.LateBg
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.PrimaryForeground
import com.iams.app.ui.theme.PresentBg
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextDisabled
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

/**
 * Panel tab enum matching RN's "detected" | "attendance"
 */
private enum class PanelTab { DETECTED, ATTENDANCE }

@Composable
fun FacultyLiveFeedScreen(
    navController: NavController,
    scheduleId: String,
    roomId: String,
    viewModel: FacultyLiveFeedViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val tracks by viewModel.tracks.collectAsState()
    val wsConnected by viewModel.wsConnected.collectAsState()
    val hybridTracks by viewModel.hybridTracks.collectAsState()
    val hybridMode by viewModel.hybridMode.collectAsState()
    val mlkitFrameSize by viewModel.mlkitFrameSize.collectAsState()
    val hudSnapshot by viewModel.hudSnapshot.collectAsState()
    val spacing = IAMSThemeTokens.spacing

    // Hybrid diagnostic HUD — hidden by default; long-press the video to toggle.
    // (Was on-by-default in debug but that cluttered the screen on low-spec devices —
    //  opt-in avoids visual noise unless the user is actively debugging.)
    var hudVisible by remember { mutableStateOf(false) }

    var activeTab by remember { mutableStateOf(PanelTab.DETECTED) }
    var showEarlyLeaveDialog by remember { mutableStateOf(false) }

    // Video-ready state: true only once WebRTC has delivered the first actual frame.
    // Gates the bounding-box overlay so detections don't appear on a black screen
    // during the ~1-3s WebRTC handshake. Reset whenever the stream URL changes.
    var isVideoReady by remember(uiState.videoUrl) { mutableStateOf(false) }

    // -- Fullscreen + zoom state --
    var isFullscreen by remember { mutableStateOf(false) }
    var zoomScale by remember { mutableStateOf(1f) }
    var zoomOffset by remember { mutableStateOf(Offset.Zero) }
    var videoBoxSize by remember { mutableStateOf(IntSize.Zero) }

    val context = LocalContext.current
    val activity = context as? Activity

    // Pinch-to-zoom gesture handler (active in fullscreen only)
    val transformableState = rememberTransformableState { zoomChange, panChange, _ ->
        zoomScale = (zoomScale * zoomChange).coerceIn(1f, 3f)
        val maxX = (zoomScale - 1) * videoBoxSize.width / 2f
        val maxY = (zoomScale - 1) * videoBoxSize.height / 2f
        zoomOffset = Offset(
            x = (zoomOffset.x + panChange.x).coerceIn(-maxX, maxX),
            y = (zoomOffset.y + panChange.y).coerceIn(-maxY, maxY)
        )
        if (zoomScale <= 1.01f) zoomOffset = Offset.Zero
    }

    // Back button exits fullscreen instead of navigating away
    BackHandler(enabled = isFullscreen) {
        isFullscreen = false
        zoomScale = 1f
        zoomOffset = Offset.Zero
    }

    // Orientation + immersive mode control
    LaunchedEffect(isFullscreen) {
        if (isFullscreen) {
            // Start landscape, but allow user to rotate freely
            activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
            activity?.window?.let { window ->
                WindowCompat.setDecorFitsSystemWindows(window, false)
                WindowInsetsControllerCompat(window, window.decorView).let { controller ->
                    controller.hide(WindowInsetsCompat.Type.systemBars())
                    controller.systemBarsBehavior =
                        WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
                }
            }
            // After a brief moment, unlock to full sensor so portrait is also allowed
            kotlinx.coroutines.delay(300)
            activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_FULL_SENSOR
        } else {
            activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
            activity?.window?.let { window ->
                WindowCompat.setDecorFitsSystemWindows(window, true)
                WindowInsetsControllerCompat(window, window.decorView)
                    .show(WindowInsetsCompat.Type.systemBars())
            }
        }
        zoomScale = 1f
        zoomOffset = Offset.Zero
    }

    // Restore orientation if screen is disposed while in fullscreen
    DisposableEffect(Unit) {
        onDispose {
            activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
            activity?.window?.let { window ->
                WindowCompat.setDecorFitsSystemWindows(window, true)
                WindowInsetsControllerCompat(window, window.decorView)
                    .show(WindowInsetsCompat.Type.systemBars())
            }
        }
    }

    // Early leave timeout config dialog
    if (showEarlyLeaveDialog) {
        EarlyLeaveTimeoutDialog(
            currentMinutes = uiState.earlyLeaveTimeoutMinutes,
            isSaving = uiState.configSaving,
            onDismiss = { showEarlyLeaveDialog = false },
            onConfirm = { minutes ->
                viewModel.updateEarlyLeaveTimeout(minutes)
                showEarlyLeaveDialog = false
            }
        )
    }

    LaunchedEffect(scheduleId, roomId) {
        viewModel.initialize(scheduleId, roomId)
    }

    // Frame dimensions from backend WebSocket (replaces ML Kit frameSize)
    val frameDimensions by viewModel.frameDimensions.collectAsState()

    val videoAspect = if (frameDimensions.first > 0 && frameDimensions.second > 0) {
        frameDimensions.first.toFloat() / frameDimensions.second.toFloat()
    } else {
        16f / 9f
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(if (isFullscreen) Color.Black else Background)
    ) {
        // Header — hidden in fullscreen
        if (!isFullscreen) {
            IAMSHeader(
                title = uiState.schedule?.subjectName ?: "Live Feed",
                onBack = { navController.popBackStack() }
            )
        }

        // Error state
        if (!isFullscreen && uiState.error != null) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.padding(spacing.xxxl)
                ) {
                    Text(
                        text = uiState.error!!,
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextSecondary,
                        textAlign = TextAlign.Center
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                    IAMSButton(
                        text = "Retry",
                        onClick = { viewModel.initialize(scheduleId, roomId) },
                        variant = IAMSButtonVariant.SECONDARY,
                        size = IAMSButtonSize.MD,
                        fullWidth = false
                    )
                }
            }
            return@Column
        }

        // Loading state — skeleton matching the final layout
        if (!isFullscreen && uiState.isLoading) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Primary)
            ) {
                // Connection status bar skeleton
                SkeletonBox(height = 28.dp, cornerRadius = 0.dp)
                // Session control bar skeleton
                SkeletonBox(height = 36.dp, cornerRadius = 0.dp, modifier = Modifier.background(Secondary))
                // Video area skeleton (55%)
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(0.55f)
                        .background(Color.Black),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator(
                            color = Color.White.copy(alpha = 0.5f),
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.height(spacing.md))
                        Text(
                            text = "Connecting to camera feed...",
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color.White.copy(alpha = 0.6f),
                            textAlign = TextAlign.Center
                        )
                    }
                }
                // Bottom panel skeleton (45%)
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(0.45f)
                        .clip(RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp))
                        .background(Background)
                ) {
                    // Drag handle
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = spacing.sm),
                        contentAlignment = Alignment.Center
                    ) {
                        SkeletonBox(width = 36.dp, height = 4.dp, cornerRadius = 2.dp)
                    }
                    // Tab bar skeleton
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = spacing.cardPadding, vertical = spacing.sm),
                        horizontalArrangement = Arrangement.SpaceEvenly
                    ) {
                        SkeletonBox(width = 80.dp, height = 14.dp)
                        SkeletonBox(width = 80.dp, height = 14.dp)
                    }
                    HorizontalDivider(color = Border, thickness = 1.dp)
                    // List items skeleton
                    Column(
                        modifier = Modifier.padding(
                            horizontal = spacing.cardPadding,
                            vertical = spacing.md
                        )
                    ) {
                        repeat(3) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = spacing.sm),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                SkeletonBox(width = 8.dp, height = 8.dp, cornerRadius = 4.dp)
                                Spacer(modifier = Modifier.width(spacing.md))
                                SkeletonBox(width = 140.dp, height = 14.dp)
                            }
                            HorizontalDivider(color = Border, thickness = 0.5.dp)
                        }
                    }
                }
            }
            return@Column
        }

        // Main content
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(if (isFullscreen) Color.Black else Primary)
        ) {
            // Connection status bar and session controls — hidden in fullscreen
            if (!isFullscreen) {
                ConnectionStatusBar(
                    isConnected = wsConnected,
                    isWaitingForCamera = uiState.videoUrl.isEmpty(),
                    detectedCount = remember(tracks, isVideoReady) {
                        if (!isVideoReady) 0
                        else tracks.count { it.status == "recognized" || it.status == "unknown" }
                    }
                )

                SessionControlBar(
                    sessionActive = uiState.sessionActive,
                    onStartSession = { viewModel.startSession() },
                    onEndSession = { viewModel.endSession() },
                    onSettingsClick = { showEarlyLeaveDialog = true },
                    sessionLoading = uiState.sessionLoading
                )
            }

            // Video feed area
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .then(
                        if (isFullscreen) Modifier.weight(1f)
                        else Modifier.aspectRatio(videoAspect)
                    )
                    .background(Color.Black)
            ) {
                // Zoomable container — zoom + pan active in fullscreen only
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .onSizeChanged { videoBoxSize = it }
                        .then(
                            if (isFullscreen) Modifier
                                .transformable(transformableState)
                                .graphicsLayer {
                                    scaleX = zoomScale
                                    scaleY = zoomScale
                                    translationX = zoomOffset.x
                                    translationY = zoomOffset.y
                                }
                            else Modifier
                        )
                ) {
                    if (uiState.videoUrl.isNotEmpty()) {
                        NativeWebRtcVideoPlayer(
                            whepUrl = uiState.videoUrl,
                            modifier = Modifier.fillMaxSize(),
                            onError = { error -> viewModel.onVideoError(error) },
                            onVideoReady = { isVideoReady = true },
                            onMlKitFacesUpdate = viewModel::onMlKitFaces,
                            onMlKitFrameSize = viewModel::onMlKitFrameSize,
                            enableMlKit = BuildConfig.HYBRID_DETECTION_ENABLED,
                        )

                        // Overlay selection: hybrid (ML Kit boxes + backend names) vs legacy
                        // (backend-authoritative interpolated boxes). The fallback controller
                        // picks BACKEND_ONLY if ML Kit is silent >2s and OFFLINE if both legs
                        // are silent — in which case we draw no overlay at all.
                        val useHybridOverlay = BuildConfig.HYBRID_DETECTION_ENABLED &&
                            hybridMode != HybridMode.BACKEND_ONLY &&
                            hybridMode != HybridMode.OFFLINE
                        val useLegacyOverlay = !BuildConfig.HYBRID_DETECTION_ENABLED ||
                            hybridMode == HybridMode.BACKEND_ONLY

                        if (useHybridOverlay) {
                            // Prefer ML Kit's reported frame dimensions (post-rotation) so the
                            // aspect-fit math matches the faces the sink actually saw. Fall back
                            // to the backend-reported size or the 896x512 default if unknown.
                            val effW = mlkitFrameSize.first
                                .takeIf { it > 0 }
                                ?: frameDimensions.first.takeIf { it > 0 }
                                ?: 896
                            val effH = mlkitFrameSize.second
                                .takeIf { it > 0 }
                                ?: frameDimensions.second.takeIf { it > 0 }
                                ?: 512
                            HybridTrackOverlay(
                                tracks = hybridTracks,
                                modifier = Modifier.fillMaxSize(),
                                videoFrameWidth = effW,
                                videoFrameHeight = effH,
                                isVideoReady = isVideoReady,
                            )
                        } else if (useLegacyOverlay) {
                            InterpolatedTrackOverlay(
                                tracks = tracks,
                                modifier = Modifier.fillMaxSize(),
                                videoFrameWidth = frameDimensions.first.takeIf { it > 0 } ?: 896,
                                videoFrameHeight = frameDimensions.second.takeIf { it > 0 } ?: 512,
                                isVideoReady = isVideoReady,
                            )
                        }

                        // Diagnostic HUD — only renders when hybrid is on AND the user hasn't
                        // toggled it off. Long-press the video area to flip. Zero cost when hidden.
                        if (BuildConfig.HYBRID_DETECTION_ENABLED) {
                            Box(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .pointerInput(Unit) {
                                        detectTapGestures(onLongPress = { hudVisible = !hudVisible })
                                    },
                            ) {
                                if (hudVisible) {
                                    HybridDiagnosticHud(
                                        snapshot = hudSnapshot,
                                        modifier = Modifier.align(Alignment.TopStart),
                                    )
                                }
                            }
                        }

                        // "Connecting..." overlay shown during WebRTC handshake
                        // (before first video frame arrives). Disappears when video is ready.
                        if (!isVideoReady && uiState.videoError == null) {
                            Box(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .background(Color.Black.copy(alpha = 0.5f)),
                                contentAlignment = Alignment.Center
                            ) {
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    CircularProgressIndicator(
                                        color = Color.White.copy(alpha = 0.7f),
                                        strokeWidth = 2.dp,
                                        modifier = Modifier.size(28.dp)
                                    )
                                    Spacer(modifier = Modifier.height(spacing.md))
                                    Text(
                                        text = "Connecting to camera…",
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = Color.White.copy(alpha = 0.85f),
                                        textAlign = TextAlign.Center
                                    )
                                }
                            }
                        }

                        if (uiState.videoError != null) {
                            Box(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .background(Color.Black.copy(alpha = 0.7f)),
                                contentAlignment = Alignment.Center
                            ) {
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    Icon(
                                        Icons.Outlined.VideocamOff,
                                        contentDescription = null,
                                        modifier = Modifier.size(48.dp),
                                        tint = AbsentFg
                                    )
                                    Spacer(modifier = Modifier.height(spacing.md))
                                    Text(
                                        text = "Camera feed error",
                                        style = MaterialTheme.typography.bodyLarge,
                                        fontWeight = FontWeight.SemiBold,
                                        color = Color.White,
                                        textAlign = TextAlign.Center
                                    )
                                    Spacer(modifier = Modifier.height(spacing.xs))
                                    Text(
                                        text = uiState.videoError!!,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = Color.White.copy(alpha = 0.7f),
                                        textAlign = TextAlign.Center,
                                        modifier = Modifier.padding(horizontal = spacing.xxl)
                                    )
                                }
                            }
                        }
                    } else {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Icon(
                                    Icons.Outlined.VideocamOff,
                                    contentDescription = null,
                                    modifier = Modifier.size(48.dp),
                                    tint = TextDisabled
                                )
                                Spacer(modifier = Modifier.height(spacing.md))
                                Text(
                                    text = "Waiting for camera",
                                    style = MaterialTheme.typography.bodyLarge,
                                    fontWeight = FontWeight.SemiBold,
                                    color = TextTertiary,
                                    textAlign = TextAlign.Center
                                )
                                Spacer(modifier = Modifier.height(spacing.sm))
                                Text(
                                    text = "The edge device is not streaming yet.\nThe feed will appear automatically once connected.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextDisabled,
                                    textAlign = TextAlign.Center,
                                    modifier = Modifier.padding(horizontal = spacing.xxl)
                                )
                            }
                        }
                    }
                }

                // Fullscreen toggle button
                IconButton(
                    onClick = { isFullscreen = !isFullscreen },
                    modifier = Modifier
                        .align(if (isFullscreen) Alignment.TopEnd else Alignment.BottomEnd)
                        .padding(8.dp)
                        .size(36.dp)
                        .background(Color.Black.copy(alpha = 0.5f), CircleShape)
                ) {
                    Icon(
                        if (isFullscreen) Icons.Default.FullscreenExit
                        else Icons.Default.Fullscreen,
                        contentDescription = "Toggle fullscreen",
                        tint = Color.White,
                        modifier = Modifier.size(20.dp)
                    )
                }
            }

            // Bottom panel — fills remaining space below video
            if (!isFullscreen) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .clip(RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp))
                    .background(Background)
            ) {
                // Drag handle indicator
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = spacing.sm),
                    contentAlignment = Alignment.Center
                ) {
                    Box(
                        modifier = Modifier
                            .width(36.dp)
                            .height(4.dp)
                            .clip(RoundedCornerShape(2.dp))
                            .background(Border)
                    )
                }

                // Tab bar
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = spacing.cardPadding)
                ) {
                    TabItem(
                        label = "Detected",
                        icon = {
                            Icon(
                                Icons.Default.People,
                                contentDescription = null,
                                modifier = Modifier.size(14.dp),
                                tint = if (activeTab == PanelTab.DETECTED) TextPrimary else TextTertiary
                            )
                        },
                        isActive = activeTab == PanelTab.DETECTED,
                        onClick = { activeTab = PanelTab.DETECTED },
                        modifier = Modifier.weight(1f)
                    )
                    TabItem(
                        label = "Attendance",
                        icon = {
                            Icon(
                                @Suppress("DEPRECATION")
                                Icons.Outlined.Assignment,
                                contentDescription = null,
                                modifier = Modifier.size(14.dp),
                                tint = if (activeTab == PanelTab.ATTENDANCE) TextPrimary else TextTertiary
                            )
                        },
                        isActive = activeTab == PanelTab.ATTENDANCE,
                        onClick = { activeTab = PanelTab.ATTENDANCE },
                        modifier = Modifier.weight(1f)
                    )
                }

                HorizontalDivider(color = Border, thickness = 1.dp)

                // Tab content
                when (activeTab) {
                    PanelTab.DETECTED -> {
                        // Detected tab header with live track count
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(
                                    horizontal = spacing.cardPadding,
                                    vertical = spacing.md
                                ),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    Icons.Default.People,
                                    contentDescription = null,
                                    modifier = Modifier.size(16.dp),
                                    tint = TextPrimary
                                )
                                Spacer(modifier = Modifier.width(spacing.sm))
                                Text(
                                    text = "Detected Students",
                                    style = MaterialTheme.typography.bodyLarge,
                                    fontWeight = FontWeight.SemiBold,
                                    color = TextPrimary
                                )
                            }
                            val recognizedCount = remember(tracks, isVideoReady) {
                                if (!isVideoReady) 0 else tracks.count { it.status == "recognized" }
                            }
                            val detectedCount = remember(tracks, isVideoReady) {
                                if (!isVideoReady) 0
                                else tracks.count { it.status == "recognized" || it.status == "unknown" }
                            }
                            Text(
                                text = "$recognizedCount recognized / $detectedCount detected",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextSecondary
                            )
                        }

                        if (isVideoReady && tracks.isEmpty() && uiState.presentStudents.isEmpty()) {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = spacing.xxl),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    text = "No students detected yet",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = TextTertiary,
                                    textAlign = TextAlign.Center
                                )
                            }
                        }
                    }
                    PanelTab.ATTENDANCE -> {
                        // Attendance tab header
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(
                                    horizontal = spacing.cardPadding,
                                    vertical = spacing.md
                                ),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "Attendance Record",
                                style = MaterialTheme.typography.bodyLarge,
                                fontWeight = FontWeight.SemiBold,
                                color = TextPrimary
                            )
                            Text(
                                text = if (isVideoReady) "${uiState.presentCount} / ${uiState.totalEnrolled}" else "— / —",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextSecondary
                            )
                        }
                    }
                }

                // Cache filtered track lists outside LazyColumn (composable scope).
                // Gated on isVideoReady — panels must stay in sync with the video feed
                // so detections aren't shown while the stream is still connecting.
                val recognizedTracks = remember(tracks, isVideoReady) {
                    if (!isVideoReady) emptyList()
                    else tracks.filter { it.status == "recognized" && it.name != null }
                }
                val unknownTracks = remember(tracks, isVideoReady) {
                    if (!isVideoReady) emptyList() else tracks.filter { it.status == "unknown" }
                }

                // Attendance list
                LazyColumn(
                    modifier = Modifier
                        .weight(1f)
                        .padding(horizontal = spacing.cardPadding)
                ) {
                    if (!isVideoReady) {
                        item {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = spacing.xxl),
                                contentAlignment = Alignment.Center
                            ) {
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    CircularProgressIndicator(
                                        color = TextTertiary,
                                        strokeWidth = 2.dp,
                                        modifier = Modifier.size(20.dp)
                                    )
                                    Spacer(modifier = Modifier.height(spacing.md))
                                    Text(
                                        text = "Waiting for camera feed…",
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = TextTertiary,
                                        textAlign = TextAlign.Center
                                    )
                                }
                            }
                        }
                    } else when (activeTab) {
                        PanelTab.DETECTED -> {
                            if (recognizedTracks.isNotEmpty()) {
                                item { AttendanceSectionLabel("Recognized (${recognizedTracks.size})", PresentFg) }
                                items(recognizedTracks, key = { it.trackId }) { track ->
                                    TrackRow(name = track.name ?: "Unknown", dotColor = PresentFg)
                                    HorizontalDivider(color = Border, thickness = 0.5.dp)
                                }
                            }
                            if (unknownTracks.isNotEmpty()) {
                                item { AttendanceSectionLabel("Unknown (${unknownTracks.size})", Color(0xFFFF9800)) }
                                items(unknownTracks, key = { it.trackId }) { track ->
                                    TrackRow(name = "Unknown", dotColor = Color(0xFFFF9800))
                                    HorizontalDivider(color = Border, thickness = 0.5.dp)
                                }
                            }
                        }
                        PanelTab.ATTENDANCE -> {
                            // Present students
                            if (uiState.presentStudents.isNotEmpty()) {
                                item { AttendanceSectionLabel("Present (${uiState.presentStudents.size})", PresentFg) }
                                items(uiState.presentStudents) { student ->
                                    StudentRow(student = student, dotColor = PresentFg)
                                    HorizontalDivider(color = Border, thickness = 0.5.dp)
                                }
                            }
                            if (uiState.lateStudents.isNotEmpty()) {
                                item { AttendanceSectionLabel("Late (${uiState.lateStudents.size})", LateFg) }
                                items(uiState.lateStudents) { student ->
                                    StudentRow(student = student, dotColor = LateFg)
                                    HorizontalDivider(color = Border, thickness = 0.5.dp)
                                }
                            }
                            // Early Leave — combine still-absent and returned
                            val allEarlyLeave = uiState.earlyLeaveStudents + uiState.earlyLeaveReturnedStudents
                            if (allEarlyLeave.isNotEmpty()) {
                                item { AttendanceSectionLabel("Early Leave (${allEarlyLeave.size})", com.iams.app.ui.theme.EarlyLeaveFg) }
                                // Still absent
                                items(uiState.earlyLeaveStudents) { student ->
                                    StudentRow(student = student, dotColor = com.iams.app.ui.theme.EarlyLeaveFg)
                                    HorizontalDivider(color = Border, thickness = 0.5.dp)
                                }
                                // Returned (with badge)
                                items(uiState.earlyLeaveReturnedStudents) { student ->
                                    EarlyLeaveReturnedRow(student = student)
                                    HorizontalDivider(color = Border, thickness = 0.5.dp)
                                }
                            }
                            if (uiState.absentStudents.isNotEmpty()) {
                                item { AttendanceSectionLabel("Absent (${uiState.absentStudents.size})", AbsentFg) }
                                items(uiState.absentStudents) { student ->
                                    StudentRow(student = student, dotColor = AbsentFg)
                                    HorizontalDivider(color = Border, thickness = 0.5.dp)
                                }
                            }
                        }
                    }
                }

                // Switch to List View button
                IAMSButton(
                    text = "Switch to List View",
                    onClick = {
                        navController.navigate(
                            com.iams.app.ui.navigation.Routes.facultyLiveAttendance(scheduleId)
                        )
                    },
                    variant = IAMSButtonVariant.OUTLINE,
                    size = IAMSButtonSize.MD,
                    fullWidth = true,
                    modifier = Modifier.padding(spacing.cardPadding)
                )

                Spacer(modifier = Modifier.height(spacing.sm))
            }
            } // end if (!isFullscreen)
        }
    }
}

// -- Sub-components -------------------------------------------------------

@Composable
private fun ConnectionStatusBar(
    isConnected: Boolean,
    isWaitingForCamera: Boolean,
    detectedCount: Int
) {
    val spacing = IAMSThemeTokens.spacing

    val bgColor = when {
        !isConnected -> AbsentBg
        isWaitingForCamera -> LateBg
        else -> PresentBg
    }
    val fgColor = when {
        !isConnected -> AbsentFg
        isWaitingForCamera -> LateFg
        else -> PresentFg
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(bgColor)
            .padding(horizontal = spacing.lg, vertical = spacing.xs),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                imageVector = if (isConnected) Icons.Default.Wifi else Icons.Default.WifiOff,
                contentDescription = null,
                modifier = Modifier.size(14.dp),
                tint = fgColor
            )
            Spacer(modifier = Modifier.width(spacing.xs))
            Text(
                text = when {
                    !isConnected -> "Reconnecting..."
                    isWaitingForCamera -> "Waiting for camera..."
                    else -> "Connected"
                },
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.SemiBold,
                color = fgColor
            )
        }

        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(spacing.sm)
        ) {
            if (isConnected) {
                LivePulse()
            }
            Text(
                text = "$detectedCount detected",
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.SemiBold,
                color = TextSecondary
            )
        }
    }
}

@Composable
private fun LivePulse() {
    val infiniteTransition = rememberInfiniteTransition(label = "livePulse")
    val scale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.5f,
        animationSpec = infiniteRepeatable(
            animation = tween(600),
            repeatMode = RepeatMode.Reverse
        ),
        label = "livePulseScale"
    )
    val liveRed = Color(0xFFF44336)

    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            modifier = Modifier
                .size(7.dp)
                .scale(scale)
                .clip(CircleShape)
                .background(liveRed)
        )
        Spacer(modifier = Modifier.width(5.dp))
        Text(
            text = "LIVE",
            color = liveRed,
            fontSize = 11.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = 1.sp
        )
    }
}

@Composable
private fun SessionControlBar(
    sessionActive: Boolean,
    onStartSession: () -> Unit,
    onEndSession: () -> Unit,
    onSettingsClick: () -> Unit,
    sessionLoading: Boolean
) {
    val spacing = IAMSThemeTokens.spacing

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Secondary)
            .padding(horizontal = spacing.lg, vertical = spacing.sm),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        if (sessionActive) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(PresentFg)
                )
                Spacer(modifier = Modifier.width(spacing.sm))
                Text(
                    text = "SESSION ACTIVE",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Bold,
                    color = PresentFg
                )
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(
                    onClick = onSettingsClick,
                    modifier = Modifier.size(32.dp)
                ) {
                    Icon(
                        Icons.Default.Settings,
                        contentDescription = "Session Settings",
                        modifier = Modifier.size(16.dp),
                        tint = TextSecondary
                    )
                }
                Spacer(modifier = Modifier.width(spacing.xs))

            Row(
                modifier = Modifier
                    .clip(RoundedCornerShape(6.dp))
                    .background(AbsentBg)
                    .clickable(enabled = !sessionLoading) { onEndSession() }
                    .padding(horizontal = spacing.md, vertical = spacing.xs),
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (sessionLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(12.dp),
                        strokeWidth = 2.dp,
                        color = AbsentFg
                    )
                } else {
                    Icon(
                        Icons.Default.Stop,
                        contentDescription = null,
                        modifier = Modifier.size(12.dp),
                        tint = AbsentFg
                    )
                    Spacer(modifier = Modifier.width(spacing.xs))
                    Text(
                        text = "End Session",
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.SemiBold,
                        color = AbsentFg
                    )
                }
            }
            } // close settings + end-session row
        } else {
            Text(
                text = "SESSION INACTIVE",
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.SemiBold,
                color = TextTertiary
            )

            Row(
                modifier = Modifier
                    .clip(RoundedCornerShape(6.dp))
                    .background(Primary)
                    .clickable(enabled = !sessionLoading) { onStartSession() }
                    .padding(horizontal = spacing.md, vertical = spacing.xs),
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (sessionLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(12.dp),
                        strokeWidth = 2.dp,
                        color = PrimaryForeground
                    )
                } else {
                    Icon(
                        Icons.Default.PlayArrow,
                        contentDescription = null,
                        modifier = Modifier.size(12.dp),
                        tint = PrimaryForeground
                    )
                    Spacer(modifier = Modifier.width(spacing.xs))
                    Text(
                        text = "Start Session",
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.SemiBold,
                        color = PrimaryForeground
                    )
                }
            }
        }
    }

    HorizontalDivider(color = Border, thickness = 1.dp)
}

@Composable
private fun TabItem(
    label: String,
    icon: @Composable () -> Unit,
    isActive: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val spacing = IAMSThemeTokens.spacing

    Column(
        modifier = modifier
            .clickable { onClick() }
            .padding(vertical = spacing.sm),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            icon()
            Spacer(modifier = Modifier.width(spacing.xs))
            Text(
                text = label,
                style = MaterialTheme.typography.bodySmall,
                fontWeight = if (isActive) FontWeight.Bold else FontWeight.Medium,
                color = if (isActive) TextPrimary else TextTertiary
            )
        }
        Spacer(modifier = Modifier.height(spacing.sm))
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(2.dp)
                .background(if (isActive) Primary else Color.Transparent)
        )
    }
}

@Composable
private fun AttendanceSectionLabel(label: String, color: Color) {
    Text(
        text = label,
        style = MaterialTheme.typography.bodySmall,
        fontWeight = FontWeight.Bold,
        color = color,
        modifier = Modifier.padding(vertical = 8.dp)
    )
}

@Composable
private fun TrackRow(
    name: String,
    dotColor: Color
) {
    val spacing = IAMSThemeTokens.spacing

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = spacing.sm),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(dotColor)
        )
        Spacer(modifier = Modifier.width(spacing.md))
        Text(
            text = name,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            color = TextPrimary,
            modifier = Modifier.weight(1f),
            maxLines = 1
        )
        // Confidence score intentionally not displayed to users
    }
}

@Composable
private fun StudentRow(
    student: StudentAttendanceStatus,
    dotColor: Color
) {
    val spacing = IAMSThemeTokens.spacing

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = spacing.sm),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(dotColor)
        )
        Spacer(modifier = Modifier.width(spacing.md))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = student.studentName,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                color = TextPrimary,
                maxLines = 1
            )
            val displayId = student.studentNumber ?: student.studentId.take(8)
            Text(
                text = displayId,
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }
        if (student.checkInTime != null) {
            Text(
                text = student.checkInTime,
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.SemiBold,
                color = TextSecondary
            )
        }
    }
}

@Composable
private fun EarlyLeaveReturnedRow(student: StudentAttendanceStatus) {
    val spacing = IAMSThemeTokens.spacing

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = spacing.sm),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(com.iams.app.ui.theme.EarlyLeaveFg.copy(alpha = 0.4f))
        )
        Spacer(modifier = Modifier.width(spacing.md))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = student.studentName,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                color = TextPrimary,
                maxLines = 1
            )
            val displayId = student.studentNumber ?: student.studentId.take(8)
            Text(
                text = displayId,
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }
        Text(
            text = "↩ Returned",
            style = MaterialTheme.typography.labelSmall,
            color = PresentFg,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier
                .clip(RoundedCornerShape(4.dp))
                .background(PresentBg)
                .padding(horizontal = 6.dp, vertical = 2.dp)
        )
    }
}

@Composable
private fun EarlyLeaveTimeoutDialog(
    currentMinutes: Int,
    isSaving: Boolean,
    onDismiss: () -> Unit,
    onConfirm: (Int) -> Unit,
) {
    var sliderValue by remember { mutableStateOf(currentMinutes.toFloat()) }
    val displayMinutes = Math.round(sliderValue)
    val spacing = IAMSThemeTokens.spacing

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text(
                text = "Early Leave Timeout",
                fontWeight = FontWeight.Bold
            )
        },
        text = {
            Column {
                Text(
                    text = "How long a student can be absent before being flagged as early leave.",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
                Spacer(modifier = Modifier.height(spacing.lg))
                Text(
                    text = "$displayMinutes minute${if (displayMinutes != 1) "s" else ""}",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary,
                    modifier = Modifier.fillMaxWidth(),
                    textAlign = TextAlign.Center
                )
                Spacer(modifier = Modifier.height(spacing.sm))
                Slider(
                    value = sliderValue,
                    onValueChange = { sliderValue = it },
                    valueRange = 1f..15f,
                    steps = 13,
                    colors = SliderDefaults.colors(
                        thumbColor = Primary,
                        activeTrackColor = Primary,
                        inactiveTrackColor = Border,
                    )
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("1 min", style = MaterialTheme.typography.labelSmall, color = TextTertiary)
                    Text("15 min", style = MaterialTheme.typography.labelSmall, color = TextTertiary)
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onConfirm(Math.round(sliderValue)) },
                enabled = !isSaving
            ) {
                Text(if (isSaving) "Saving..." else "Save", color = Primary)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel", color = TextSecondary)
            }
        }
    )
}
