package com.iams.app.ui.faculty

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material.icons.filled.WifiOff
import androidx.compose.material.icons.outlined.Assignment
import androidx.compose.material.icons.outlined.VideocamOff
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.StudentAttendanceStatus
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.NativeWebRtcVideoPlayer
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.components.TrackOverlay
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
    val spacing = IAMSThemeTokens.spacing

    var activeTab by remember { mutableStateOf(PanelTab.DETECTED) }

    LaunchedEffect(scheduleId, roomId) {
        viewModel.initialize(scheduleId, roomId)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        // Header
        IAMSHeader(
            title = uiState.schedule?.subjectName ?: "Live Feed",
            onBack = { navController.popBackStack() }
        )

        // Error state
        if (uiState.error != null) {
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

        // Loading state
        if (uiState.isLoading) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    CircularProgressIndicator(color = Primary)
                    Spacer(modifier = Modifier.height(spacing.md))
                    Text(
                        text = "Connecting to camera feed...",
                        style = MaterialTheme.typography.bodyMedium,
                        color = TextSecondary,
                        textAlign = TextAlign.Center
                    )
                }
            }
            return@Column
        }

        // Main content
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(Primary)
        ) {
            // Connection status bar
            ConnectionStatusBar(
                isConnected = wsConnected,
                isWaitingForCamera = uiState.videoUrl.isEmpty(),
                presentCount = uiState.presentCount,
                totalEnrolled = uiState.totalEnrolled,
                fps = uiState.fps,
                processingMs = uiState.processingMs
            )

            // Session control bar
            SessionControlBar(
                sessionActive = true,
                onStartSession = { },
                onEndSession = { },
                sessionLoading = false
            )

            // Video feed area (~55%)
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(0.55f)
                    .background(Color.Black)
            ) {
                if (uiState.videoUrl.isNotEmpty()) {
                    NativeWebRtcVideoPlayer(
                        whepUrl = uiState.videoUrl,
                        modifier = Modifier.fillMaxSize(),
                        onError = { error -> viewModel.onVideoError(error) }
                    )

                    // Track overlay from backend pipeline (replaces ML Kit + FaceOverlay)
                    TrackOverlay(
                        tracks = tracks,
                        modifier = Modifier.fillMaxSize()
                    )

                    // Show video error overlay if playback failed
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
                    // No video URL -- waiting for camera
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

            // Bottom panel (~45%)
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(0.45f)
                    .clip(RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp))
                    .background(Background)
            ) {
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
                            Text(
                                text = "${tracks.count { it.status == "recognized" }} recognized / ${tracks.size} detected",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextSecondary
                            )
                        }

                        if (tracks.isEmpty() && uiState.presentStudents.isEmpty()) {
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
                                text = "${uiState.presentCount} / ${uiState.totalEnrolled}",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextSecondary
                            )
                        }
                    }
                }

                // Attendance list
                LazyColumn(
                    modifier = Modifier
                        .weight(1f)
                        .padding(horizontal = spacing.cardPadding)
                ) {
                    when (activeTab) {
                        PanelTab.DETECTED -> {
                            // Show currently tracked faces from real-time data
                            val recognized = tracks.filter { it.status == "recognized" && it.name != null }
                            val unknown = tracks.filter { it.status != "recognized" }

                            if (recognized.isNotEmpty()) {
                                item { AttendanceSectionLabel("Recognized (${recognized.size})", PresentFg) }
                                items(recognized, key = { it.trackId }) { track ->
                                    TrackRow(name = track.name ?: "Unknown", confidence = track.confidence, dotColor = PresentFg)
                                    HorizontalDivider(color = Border, thickness = 0.5.dp)
                                }
                            }
                            if (unknown.isNotEmpty()) {
                                item { AttendanceSectionLabel("Unknown (${unknown.size})", Color(0xFFFF9800)) }
                                items(unknown, key = { it.trackId }) { track ->
                                    TrackRow(name = "Unknown", confidence = track.confidence, dotColor = Color(0xFFFF9800))
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
                            if (uiState.earlyLeaveStudents.isNotEmpty()) {
                                item { AttendanceSectionLabel("Early Leave (${uiState.earlyLeaveStudents.size})", com.iams.app.ui.theme.EarlyLeaveFg) }
                                items(uiState.earlyLeaveStudents) { student ->
                                    StudentRow(student = student, dotColor = com.iams.app.ui.theme.EarlyLeaveFg)
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
                    onClick = { /* Navigate to LiveAttendance list screen */ },
                    variant = IAMSButtonVariant.OUTLINE,
                    size = IAMSButtonSize.MD,
                    fullWidth = true,
                    modifier = Modifier.padding(spacing.cardPadding)
                )

                Spacer(modifier = Modifier.height(spacing.sm))
            }
        }
    }
}

// -- Sub-components -------------------------------------------------------

@Composable
private fun ConnectionStatusBar(
    isConnected: Boolean,
    isWaitingForCamera: Boolean,
    presentCount: Int,
    totalEnrolled: Int,
    fps: Float,
    processingMs: Float
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
            if (fps > 0) {
                Text(
                    text = "${fps.toInt()}fps ${processingMs.toInt()}ms",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
            }
            if (presentCount > 0) {
                Text(
                    text = "$presentCount detected",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                    color = TextSecondary
                )
            }
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
    confidence: Float,
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
        if (confidence > 0.01f) {
            Text(
                text = "${(confidence * 100).toInt()}%",
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.SemiBold,
                color = TextSecondary
            )
        }
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
            Text(
                text = student.studentId,
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
