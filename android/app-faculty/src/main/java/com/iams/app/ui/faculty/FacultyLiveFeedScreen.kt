package com.iams.app.ui.faculty

import android.app.Activity
import android.content.pm.ActivityInfo
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Fullscreen
import androidx.compose.material.icons.filled.FullscreenExit
import androidx.compose.material.icons.outlined.AccessTime
import androidx.compose.material.icons.outlined.MeetingRoom
import androidx.compose.material.icons.outlined.VideocamOff
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.NativeWebRtcVideoPlayer
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.PresentBorder
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import java.time.LocalTime
import java.time.format.DateTimeFormatter

/**
 * Faculty Live Feed — pure WebRTC viewer (2026-04-22 two-app split).
 *
 * Portrait layout:
 *  • Top bar: back arrow + subject title/subtitle (under status bar)
 *  • Video: 16:9 black surface flush under the top bar, with LIVE badge
 *    (top-left) and fullscreen toggle (bottom-right)
 *  • Session details card: subject, subject code, room, time range +
 *    time-state chip (Live / Upcoming / Completed)
 *  • Stream-source footer at screen bottom
 *
 * Fullscreen: rotates to landscape, hides system bars, video fills the
 * screen, only the fullscreen-exit icon is visible.
 */
@Composable
fun FacultyLiveFeedScreen(
    navController: NavController,
    scheduleId: String,
    roomId: String,
    viewModel: FacultyLiveFeedViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing
    val context = LocalContext.current
    val activity = context as? Activity

    var isFullscreen by remember { mutableStateOf(false) }

    LaunchedEffect(scheduleId, roomId) {
        viewModel.load(scheduleId, roomId)
    }

    // Toggle device orientation + system UI for fullscreen video.
    DisposableEffect(isFullscreen) {
        val a = activity
        if (a != null) {
            if (isFullscreen) {
                a.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
                WindowCompat.getInsetsController(a.window, a.window.decorView).apply {
                    systemBarsBehavior =
                        WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
                    hide(WindowInsetsCompat.Type.systemBars())
                }
            } else {
                a.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
                WindowCompat.getInsetsController(a.window, a.window.decorView)
                    .show(WindowInsetsCompat.Type.systemBars())
            }
        }
        onDispose {
            val d = activity
            if (d != null) {
                d.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
                WindowCompat.getInsetsController(d.window, d.window.decorView)
                    .show(WindowInsetsCompat.Type.systemBars())
            }
        }
    }

    BackHandler(enabled = isFullscreen) { isFullscreen = false }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(if (isFullscreen) Color.Black else Background),
    ) {
        when {
            uiState.isLoading -> LoadingState()
            uiState.error != null -> ErrorState(
                message = uiState.error ?: "",
                onBack = { navController.popBackStack() },
            )
            uiState.whepUrl.isNotBlank() -> {
                if (isFullscreen) {
                    FullscreenPlayer(
                        whepUrl = uiState.whepUrl,
                        onExitFullscreen = { isFullscreen = false },
                    )
                } else {
                    PortraitPlayer(
                        uiState = uiState,
                        onBack = { navController.popBackStack() },
                        onEnterFullscreen = { isFullscreen = true },
                    )
                }
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Portrait layout
// ─────────────────────────────────────────────────────────────────────────

@Composable
private fun PortraitPlayer(
    uiState: FacultyLiveFeedUiState,
    onBack: () -> Unit,
    onEnterFullscreen: () -> Unit,
) {
    val spacing = IAMSThemeTokens.spacing
    val schedule = uiState.schedule
    val roomName = uiState.room?.name ?: schedule?.roomName

    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding(),
    ) {
        // ── Top bar: back arrow + subject title/subtitle ──
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = spacing.xs, vertical = spacing.xs),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(
                    Icons.AutoMirrored.Filled.ArrowBack,
                    contentDescription = "Back",
                    tint = TextPrimary,
                )
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = schedule?.subjectName ?: "Live Feed",
                    color = TextPrimary,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (!roomName.isNullOrBlank()) {
                    Text(
                        text = roomName,
                        color = TextSecondary,
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            // Right-side spacer so the title stays visually centered
            // relative to the back arrow's footprint.
            Spacer(modifier = Modifier.width(48.dp))
        }

        HorizontalDivider(color = Border)

        // Scrollable middle section (video + details) so nothing clips
        // on short phones. Footer is anchored below the scroll region.
        Column(
            modifier = Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState()),
        ) {
            // ── Video (16:9, black, flush under top bar) ──
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(16f / 9f)
                    .background(Color.Black),
            ) {
                NativeWebRtcVideoPlayer(
                    whepUrl = uiState.whepUrl,
                    modifier = Modifier.fillMaxSize(),
                )

                // LIVE badge (top-left, overlays video)
                LiveBadge(
                    modifier = Modifier
                        .align(Alignment.TopStart)
                        .padding(spacing.sm),
                )

                // Fullscreen button (bottom-right)
                Surface(
                    shape = CircleShape,
                    color = Color.Black.copy(alpha = 0.55f),
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .padding(spacing.sm),
                ) {
                    IconButton(
                        onClick = onEnterFullscreen,
                        modifier = Modifier.size(40.dp),
                    ) {
                        Icon(
                            imageVector = Icons.Filled.Fullscreen,
                            contentDescription = "Fullscreen",
                            tint = Color.White,
                            modifier = Modifier.size(20.dp),
                        )
                    }
                }
            }

            // ── Session details card ──
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = spacing.lg),
            ) {
                Spacer(modifier = Modifier.height(spacing.lg))
                SessionDetailsCard(uiState = uiState)
                Spacer(modifier = Modifier.height(spacing.lg))
            }
        }

        // ── Footer: stream source (pinned above the nav bar) ──
        Text(
            text = "Stream from VPS mediamtx · live ≤ 1 s latency",
            color = TextTertiary,
            style = MaterialTheme.typography.bodySmall,
            fontSize = 12.sp,
            textAlign = TextAlign.Center,
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(horizontal = spacing.lg, vertical = spacing.md),
        )
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Fullscreen layout
// ─────────────────────────────────────────────────────────────────────────

@Composable
private fun FullscreenPlayer(
    whepUrl: String,
    onExitFullscreen: () -> Unit,
) {
    val spacing = IAMSThemeTokens.spacing
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black),
    ) {
        NativeWebRtcVideoPlayer(
            whepUrl = whepUrl,
            modifier = Modifier.fillMaxSize(),
        )
        Surface(
            shape = CircleShape,
            color = Color.Black.copy(alpha = 0.55f),
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(spacing.md),
        ) {
            IconButton(
                onClick = onExitFullscreen,
                modifier = Modifier.size(44.dp),
            ) {
                Icon(
                    imageVector = Icons.Filled.FullscreenExit,
                    contentDescription = "Exit fullscreen",
                    tint = Color.White,
                    modifier = Modifier.size(22.dp),
                )
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Session details card
// ─────────────────────────────────────────────────────────────────────────

@Composable
private fun SessionDetailsCard(uiState: FacultyLiveFeedUiState) {
    val spacing = IAMSThemeTokens.spacing
    val radius = IAMSThemeTokens.radius
    val schedule = uiState.schedule
    val room = uiState.room

    val timeState = schedule?.let { computeTimeState(it.startTime, it.endTime) }
    val isLive = timeState == LiveFeedTimeState.ACTIVE

    val borderColor = if (isLive) PresentBorder else Border
    val borderWidth = if (isLive) 1.5.dp else 1.dp

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = radius.cardShape,
        color = Background,
        border = androidx.compose.foundation.BorderStroke(borderWidth, borderColor),
        shadowElevation = 0.dp,
    ) {
        Column(modifier = Modifier.padding(spacing.cardPadding)) {
            // Status chip
            Row(verticalAlignment = Alignment.CenterVertically) {
                val (label, color) = when (timeState) {
                    LiveFeedTimeState.ACTIVE -> "LIVE NOW" to PresentFg
                    LiveFeedTimeState.UPCOMING -> "UPCOMING" to TextTertiary
                    LiveFeedTimeState.COMPLETED -> "COMPLETED" to TextTertiary
                    null -> "SESSION" to TextTertiary
                }
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(color),
                )
                Spacer(modifier = Modifier.width(spacing.sm))
                Text(
                    text = label,
                    style = MaterialTheme.typography.bodySmall.copy(letterSpacing = 0.5.sp),
                    fontWeight = FontWeight.SemiBold,
                    color = color,
                )
            }

            Spacer(modifier = Modifier.height(spacing.md))

            // Subject name
            Text(
                text = schedule?.subjectName ?: "Live stream",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = Primary,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )

            if (!schedule?.subjectCode.isNullOrBlank()) {
                Spacer(modifier = Modifier.height(spacing.xs))
                Text(
                    text = schedule?.subjectCode ?: "",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary,
                )
            }

            Spacer(modifier = Modifier.height(spacing.md))

            // Room
            val roomLabel = room?.name ?: schedule?.roomName
            if (!roomLabel.isNullOrBlank()) {
                DetailRow(
                    icon = Icons.Outlined.MeetingRoom,
                    label = roomLabel,
                )
            }

            // Time range
            if (schedule != null) {
                Spacer(modifier = Modifier.height(spacing.sm))
                DetailRow(
                    icon = Icons.Outlined.AccessTime,
                    label = "${formatTime(schedule.startTime)} - ${formatTime(schedule.endTime)}",
                )
            }
        }
    }
}

@Composable
private fun DetailRow(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
) {
    val spacing = IAMSThemeTokens.spacing
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = TextSecondary,
            modifier = Modifier.size(18.dp),
        )
        Spacer(modifier = Modifier.width(spacing.sm))
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = TextSecondary,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

// ─────────────────────────────────────────────────────────────────────────
// LIVE badge
// ─────────────────────────────────────────────────────────────────────────

@Composable
private fun LiveBadge(modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(4.dp),
        color = Color(0xFFE11D48), // rose-600
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(6.dp)
                    .clip(CircleShape)
                    .background(Color.White),
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = "LIVE",
                color = Color.White,
                style = MaterialTheme.typography.labelSmall.copy(letterSpacing = 1.sp),
                fontWeight = FontWeight.Bold,
            )
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Loading / Error states
// ─────────────────────────────────────────────────────────────────────────

@Composable
private fun LoadingState() {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding()
            .navigationBarsPadding(),
        contentAlignment = Alignment.Center,
    ) { CircularProgressIndicator() }
}

@Composable
private fun ErrorState(message: String, onBack: () -> Unit) {
    val spacing = IAMSThemeTokens.spacing
    Column(
        modifier = Modifier
            .fillMaxSize()
            .statusBarsPadding()
            .navigationBarsPadding()
            .padding(spacing.xl),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(
            imageVector = Icons.Outlined.VideocamOff,
            contentDescription = null,
            tint = TextSecondary,
            modifier = Modifier.size(48.dp),
        )
        Spacer(Modifier.height(spacing.md))
        Text(
            text = "Stream unavailable",
            color = TextPrimary,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(Modifier.height(spacing.sm))
        Text(
            text = message.ifBlank { "We couldn't reach the camera feed. Please try again." },
            color = TextSecondary,
            style = MaterialTheme.typography.bodyMedium,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(spacing.lg))
        IAMSButton(
            text = "Back to schedules",
            onClick = onBack,
            variant = IAMSButtonVariant.SECONDARY,
            size = IAMSButtonSize.MD,
            fullWidth = false,
        )
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Time-state helpers (local to this screen; schedules screen has its own)
// ─────────────────────────────────────────────────────────────────────────

private enum class LiveFeedTimeState { COMPLETED, ACTIVE, UPCOMING }

private fun computeTimeState(startTime: String, endTime: String): LiveFeedTimeState {
    val now = LocalTime.now()
    val start = parseTime(startTime) ?: return LiveFeedTimeState.UPCOMING
    val end = parseTime(endTime) ?: return LiveFeedTimeState.UPCOMING
    return when {
        now.isAfter(end) -> LiveFeedTimeState.COMPLETED
        now.isBefore(start) -> LiveFeedTimeState.UPCOMING
        else -> LiveFeedTimeState.ACTIVE
    }
}

private fun parseTime(time: String): LocalTime? {
    return runCatching { LocalTime.parse(time) }.getOrNull()
        ?: runCatching {
            val parts = time.split(":")
            LocalTime.of(parts[0].toInt(), parts[1].toInt())
        }.getOrNull()
}

private fun formatTime(timeStr: String): String {
    val time = parseTime(timeStr) ?: return timeStr
    val hours = time.hour
    val minutes = time.minute
    val period = if (hours >= 12) "PM" else "AM"
    val displayHours = if (hours % 12 == 0) 12 else hours % 12
    return "$displayHours:${minutes.toString().padStart(2, '0')} $period"
}
