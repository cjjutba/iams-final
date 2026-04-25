package com.iams.app.ui.student

import com.iams.app.ui.components.NotificationBellButton
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.ui.graphics.Color
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.AttendanceRecordResponse
import com.iams.app.data.model.ScheduleResponse
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
import com.iams.app.ui.components.AttendanceStatus
import com.iams.app.ui.components.CardSkeleton
import com.iams.app.ui.components.SkeletonBox
import com.iams.app.ui.components.IAMSBadge
import com.iams.app.ui.utils.parseAttendanceStatus
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.AbsentBg
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.LateBg
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.PresentBorder
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.StatusLateFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudentHomeScreen(
    navController: NavController,
    viewModel: StudentHomeViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val notifUnreadCount by viewModel.notificationService.unreadCount.collectAsState()
    val connectionHealth by viewModel.connectionHealth.collectAsState()
    val spacing = IAMSThemeTokens.spacing
    val toastState = LocalToastState.current

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            toastState.showToast(it, ToastType.ERROR)
            viewModel.clearError()
        }
    }

    // Error state with no cached data
    if (uiState.error != null && uiState.todaySchedules.isEmpty() && !uiState.isLoading) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(Background)
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = spacing.xxl),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        Icons.Default.Refresh,
                        contentDescription = null,
                        modifier = Modifier.size(40.dp),
                        tint = TextTertiary
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                    Text(
                        text = "Unable to load your schedule. Please try again.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextSecondary,
                        textAlign = TextAlign.Center
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                    IAMSButton(
                        text = "Retry",
                        onClick = {
                            viewModel.clearError()
                            viewModel.loadData()
                        },
                        variant = IAMSButtonVariant.SECONDARY,
                        size = IAMSButtonSize.MD,
                        fullWidth = false
                    )
                }
            }
        }
        return
    }

    val currentClass = uiState.currentClass
    val otherSchedules = uiState.todaySchedules.filter { it.id != currentClass?.id }
    // "Upcoming" means strictly future — schedules whose start time has not
    // arrived yet. ACTIVE sessions other than `currentClass` (e.g. overlapping
    // rolling test sessions) are intentionally excluded: the user reserves
    // this section for classes that are coming up next, not for anything
    // already in progress. Completed classes get their own section below.
    val upcomingSchedules = otherSchedules
        .filter { viewModel.getScheduleTimeState(it) == ScheduleTimeState.UPCOMING }
        .sortedBy { it.startTime }
    val completedSchedules = otherSchedules
        .filter { viewModel.getScheduleTimeState(it) == ScheduleTimeState.COMPLETED }
        .sortedByDescending { it.startTime }

    PullToRefreshBox(
        isRefreshing = uiState.isRefreshing,
        onRefresh = { viewModel.refresh() },
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = spacing.lg),
        ) {
            // ── Real-time connection banner ──
            // Hidden when CONNECTED; surfaces reconnecting / offline so
            // students know whether their attendance updates are live
            // without having to guess or pull-to-refresh.
            item {
                RealtimeConnectionBanner(health = connectionHealth)
            }

            // ── Header: greeting + notification bell + date ──
            item {
                Spacer(modifier = Modifier.height(spacing.lg))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "${viewModel.getGreeting()}, ${uiState.user?.firstName ?: "Student"}!",
                        style = MaterialTheme.typography.headlineLarge,
                        fontWeight = FontWeight.Bold,
                        color = Primary,
                        modifier = Modifier.weight(1f)
                    )
                    NotificationBellButton(
                        notificationService = viewModel.notificationService,
                        onClick = { navController.navigate(Routes.STUDENT_NOTIFICATIONS) },
                    )
                }

                Spacer(modifier = Modifier.height(spacing.sm))

                Text(
                    text = LocalDate.now().format(
                        DateTimeFormatter.ofPattern("EEEE, MMMM d, yyyy", Locale.getDefault())
                    ),
                    style = MaterialTheme.typography.bodyLarge,
                    color = TextSecondary
                )
            }

            // ── Loading skeletons ──
            if (uiState.isLoading) {
                // Stats row skeleton
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(IntrinsicSize.Min),
                        horizontalArrangement = Arrangement.spacedBy(spacing.sm)
                    ) {
                        repeat(3) {
                            IAMSCard(modifier = Modifier.weight(1f).fillMaxHeight()) {
                                SkeletonBox(width = 48.dp, height = 28.dp, cornerRadius = 4.dp)
                                Spacer(modifier = Modifier.height(4.dp))
                                SkeletonBox(width = 64.dp, height = 12.dp)
                            }
                        }
                    }
                }
                // Hero card skeleton
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    IAMSCard {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            SkeletonBox(width = 8.dp, height = 8.dp, cornerRadius = 4.dp)
                            Spacer(modifier = Modifier.width(spacing.sm))
                            SkeletonBox(width = 100.dp, height = 12.dp)
                        }
                        Spacer(modifier = Modifier.height(spacing.md))
                        SkeletonBox(width = 200.dp, height = 22.dp)
                        Spacer(modifier = Modifier.height(spacing.xs))
                        SkeletonBox(width = 240.dp, height = 14.dp)
                    }
                }
                // Schedule cards skeleton
                items(2) {
                    Spacer(modifier = Modifier.height(spacing.sm))
                    CardSkeleton()
                }
            }

            // ── Face uploading / not registered warning ──
            if (!uiState.isLoading && uiState.faceUploading) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    FaceUploadingCard()
                }
            } else if (!uiState.isLoading && uiState.faceRegistered == false) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    FaceNotRegisteredCard(
                        onRegisterClick = {
                            navController.navigate(Routes.studentFaceRegister("register"))
                        }
                    )
                }
            }

            // ── Attendance rate + quick stats row ──
            if (!uiState.isLoading && uiState.attendanceSummary != null) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    AttendanceStatsRow(
                        attendanceRate = uiState.attendanceSummary!!.attendanceRate,
                        totalClasses = uiState.attendanceSummary!!.totalClasses,
                        presentCount = uiState.attendanceSummary!!.presentCount,
                        lateCount = uiState.attendanceSummary!!.lateCount
                    )
                }
            }

            // ── Current class hero card ──
            if (!uiState.isLoading && currentClass != null) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    CurrentClassCard(
                        schedule = currentClass,
                        todayStatus = viewModel.getTodayStatus(currentClass.id),
                        formatTime = { viewModel.formatTime(it) }
                    )
                }
            }

            // ── Upcoming class card (only when no current class) ──
            if (!uiState.isLoading && currentClass == null && uiState.nextClass != null) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    UpcomingClassCard(
                        schedule = uiState.nextClass!!,
                        minutesUntilStart = viewModel.getMinutesUntilStart(uiState.nextClass!!),
                        formatTime = { viewModel.formatTime(it) }
                    )
                }
            }

            // ── Loading header placeholder ──
            if (uiState.isLoading) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    Text(
                        text = "Upcoming",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = Primary
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                }
            }

            // ── Empty / single-class fallbacks ──
            if (!uiState.isLoading && uiState.todaySchedules.isEmpty()) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    EmptyScheduleState(viewModel = viewModel)
                }
            } else if (!uiState.isLoading && otherSchedules.isEmpty() && currentClass != null) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    Text(
                        text = "This is your only class today.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = TextTertiary,
                        textAlign = TextAlign.Center,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = spacing.xl)
                    )
                }
            }

            // ── Upcoming section ──
            if (!uiState.isLoading && upcomingSchedules.isNotEmpty()) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    Text(
                        text = "Upcoming (${upcomingSchedules.size})",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = Primary
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                }
                items(upcomingSchedules, key = { "upcoming-${it.id}" }) { schedule ->
                    TodayScheduleCard(
                        schedule = schedule,
                        timeState = viewModel.getScheduleTimeState(schedule),
                        minutesUntilStart = viewModel.getMinutesUntilStart(schedule),
                        todayStatus = viewModel.getTodayStatus(schedule.id),
                        formatTime = { viewModel.formatTime(it) }
                    )
                    Spacer(modifier = Modifier.height(spacing.sm))
                }
            }

            // ── Completed section ──
            if (!uiState.isLoading && completedSchedules.isNotEmpty()) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    Text(
                        text = "Completed (${completedSchedules.size})",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = Primary
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                }
                items(completedSchedules, key = { "completed-${it.id}" }) { schedule ->
                    TodayScheduleCard(
                        schedule = schedule,
                        timeState = viewModel.getScheduleTimeState(schedule),
                        minutesUntilStart = viewModel.getMinutesUntilStart(schedule),
                        todayStatus = viewModel.getTodayStatus(schedule.id),
                        formatTime = { viewModel.formatTime(it) }
                    )
                    Spacer(modifier = Modifier.height(spacing.sm))
                }
            }

            // ── Recent activity ──
            if (uiState.recentActivity.isNotEmpty()) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    Text(
                        text = "Recent Activity",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = Primary
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                }

                items(uiState.recentActivity, key = { it.id }) { record ->
                    ActivityFeedItem(
                        record = record,
                        viewModel = viewModel
                    )
                    Spacer(modifier = Modifier.height(spacing.sm))
                }
            }

            // Bottom spacing
            item {
                Spacer(modifier = Modifier.height(spacing.xxl))
            }
        }
    }
}

// ── Face Uploading Card (shown while pending face images are being uploaded) ──

@Composable
private fun FaceUploadingCard() {
    val spacing = IAMSThemeTokens.spacing

    IAMSCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            CircularProgressIndicator(
                modifier = Modifier.size(20.dp),
                strokeWidth = 2.dp,
                color = Primary
            )
            Spacer(modifier = Modifier.width(spacing.md))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "Registering Your Face...",
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = Primary
                )
                Text(
                    text = "Uploading face data captured during registration",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
            }
        }
    }
}

// ── Face Not Registered Card (only shown when NOT registered) ──

@Composable
private fun FaceNotRegisteredCard(
    onRegisterClick: () -> Unit
) {
    val spacing = IAMSThemeTokens.spacing

    IAMSCard(onClick = onRegisterClick) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = Icons.Default.Warning,
                contentDescription = null,
                modifier = Modifier.size(20.dp),
                tint = AbsentFg
            )
            Spacer(modifier = Modifier.width(spacing.md))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "Face Not Registered",
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = AbsentFg
                )
                Text(
                    text = "Register your face to enable attendance tracking",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
            }
        }
    }
}

// ── Attendance Stats Row ──

@Composable
private fun AttendanceStatsRow(
    attendanceRate: Float,
    totalClasses: Int,
    presentCount: Int,
    lateCount: Int
) {
    val spacing = IAMSThemeTokens.spacing
    val ratePercent = (attendanceRate * 100).toInt()
    val rateColor = when {
        ratePercent >= 80 -> PresentFg
        ratePercent >= 60 -> LateFg
        else -> AbsentFg
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(IntrinsicSize.Min),
        horizontalArrangement = Arrangement.spacedBy(spacing.sm)
    ) {
        // Attendance rate
        IAMSCard(modifier = Modifier.weight(1f).fillMaxHeight()) {
            Text(
                text = "${ratePercent}%",
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold,
                color = rateColor
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = "Attendance",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }

        // Present count
        IAMSCard(modifier = Modifier.weight(1f).fillMaxHeight()) {
            Text(
                text = "$presentCount",
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold,
                color = PresentFg
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = "Present",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }

        // Classes count
        IAMSCard(modifier = Modifier.weight(1f).fillMaxHeight()) {
            Text(
                text = "$totalClasses",
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = "Classes",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }
    }
}

// ── Current Class Card ──

@Composable
private fun CurrentClassCard(
    schedule: ScheduleResponse,
    todayStatus: String?,
    formatTime: (String) -> String
) {
    val spacing = IAMSThemeTokens.spacing
    val radius = IAMSThemeTokens.radius

    val borderColor = if (todayStatus == "present") PresentBorder else Border

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = radius.cardShape,
        color = Background,
        border = BorderStroke(if (todayStatus == "present") 1.5.dp else 1.dp, borderColor),
        shadowElevation = 0.dp,
    ) {
        Column(modifier = Modifier.padding(spacing.cardPadding)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(PresentFg)
                    )
                    Spacer(modifier = Modifier.width(spacing.sm))
                    Text(
                        text = "CURRENT CLASS",
                        style = MaterialTheme.typography.bodySmall.copy(
                            letterSpacing = 0.5.sp
                        ),
                        fontWeight = FontWeight.SemiBold,
                        color = PresentFg
                    )
                }

                // Attendance status indicator — always rendered as a
                // colored pill so the visual cue matches the rest of the
                // app (History, Detail, Activity feed) instead of a
                // bespoke text-only variant that ignored EARLY_LEAVE.
                if (todayStatus != null) {
                    IAMSBadge(status = parseAttendanceStatus(todayStatus))
                }
            }

            Spacer(modifier = Modifier.height(spacing.md))

            Text(
                text = schedule.subjectName,
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = Primary
            )

            Spacer(modifier = Modifier.height(spacing.xs))

            Text(
                text = "${schedule.roomName ?: "No room"} \u2022 ${formatTime(schedule.startTime)} - ${formatTime(schedule.endTime)}",
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary
            )
        }
    }
}

// ── Upcoming Class Card ──

@Composable
private fun UpcomingClassCard(
    schedule: ScheduleResponse,
    minutesUntilStart: Long,
    formatTime: (String) -> String
) {
    val spacing = IAMSThemeTokens.spacing
    val radius = IAMSThemeTokens.radius

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = radius.cardShape,
        color = Background,
        border = BorderStroke(1.dp, Border),
        shadowElevation = 0.dp,
    ) {
        Column(modifier = Modifier.padding(spacing.cardPadding)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Outlined.Schedule,
                        contentDescription = null,
                        modifier = Modifier.size(14.dp),
                        tint = TextTertiary
                    )
                    Spacer(modifier = Modifier.width(spacing.xs))
                    Text(
                        text = "UPCOMING",
                        style = MaterialTheme.typography.bodySmall.copy(
                            letterSpacing = 0.5.sp
                        ),
                        fontWeight = FontWeight.SemiBold,
                        color = TextTertiary
                    )
                }
                Text(
                    text = if (minutesUntilStart <= 60) "in ${minutesUntilStart} min" else "Later today",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
            }

            Spacer(modifier = Modifier.height(spacing.md))

            Text(
                text = schedule.subjectName,
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.SemiBold,
                color = Primary
            )

            Spacer(modifier = Modifier.height(spacing.xs))

            Text(
                text = "${formatTime(schedule.startTime)} - ${formatTime(schedule.endTime)} \u2022 ${schedule.roomName ?: "No room"}",
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary
            )
        }
    }
}

// ── Today Schedule Card ──

@Composable
private fun TodayScheduleCard(
    schedule: ScheduleResponse,
    timeState: ScheduleTimeState,
    minutesUntilStart: Long,
    todayStatus: String?,
    formatTime: (String) -> String
) {
    val spacing = IAMSThemeTokens.spacing

    IAMSCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "${formatTime(schedule.startTime)} - ${formatTime(schedule.endTime)}",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary
                )
                Spacer(modifier = Modifier.height(spacing.xs))
                Text(
                    text = schedule.subjectName,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = Primary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Spacer(modifier = Modifier.height(spacing.xs))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = schedule.roomName ?: "",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextSecondary
                    )
                    // Show attendance status for completed classes
                    if (timeState == ScheduleTimeState.COMPLETED && todayStatus != null) {
                        Text(
                            text = " \u2022 ",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary
                        )
                        val (label, color) = when (todayStatus.lowercase()) {
                            "present" -> "Present" to PresentFg
                            "late" -> "Late" to StatusLateFg
                            "absent" -> "Absent" to AbsentFg
                            else -> todayStatus to TextSecondary
                        }
                        Text(
                            text = label,
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.SemiBold,
                            color = color
                        )
                    }
                }
            }

            // Right: time state
            Text(
                text = when (timeState) {
                    ScheduleTimeState.COMPLETED -> "Completed"
                    ScheduleTimeState.UPCOMING -> if (minutesUntilStart <= 60) "in ${minutesUntilStart} min" else "Upcoming"
                    ScheduleTimeState.ACTIVE -> "Now"
                },
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.Medium,
                color = when (timeState) {
                    ScheduleTimeState.COMPLETED -> TextTertiary
                    ScheduleTimeState.UPCOMING -> TextSecondary
                    ScheduleTimeState.ACTIVE -> PresentFg
                }
            )
        }
    }
}

// ── Empty Schedule State ──

@Composable
private fun EmptyScheduleState(viewModel: StudentHomeViewModel) {
    val spacing = IAMSThemeTokens.spacing
    val radius = IAMSThemeTokens.radius
    val nextDay = viewModel.getNextDayWithClasses()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = spacing.xxxl),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "No classes scheduled for today",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = TextAlign.Center
        )

        if (nextDay != null) {
            Spacer(modifier = Modifier.height(spacing.lg))
            Text(
                text = "Next classes on ${getDayName(nextDay.first)}",
                style = MaterialTheme.typography.bodyMedium,
                color = TextTertiary,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(spacing.sm))

            val previewSchedules = nextDay.second.take(3)
            previewSchedules.forEach { schedule ->
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = spacing.sm),
                    shape = radius.cardShape,
                    color = Background,
                    border = BorderStroke(1.dp, Border),
                    shadowElevation = 0.dp,
                ) {
                    Column(
                        modifier = Modifier.padding(
                            horizontal = spacing.cardPadding,
                            vertical = spacing.sm
                        )
                    ) {
                        Text(
                            text = schedule.subjectName,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = Primary,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        Text(
                            text = buildString {
                                append(viewModel.formatTime(schedule.startTime))
                                append(" - ")
                                append(viewModel.formatTime(schedule.endTime))
                                if (!schedule.roomName.isNullOrBlank()) {
                                    append(" \u2022 ")
                                    append(schedule.roomName)
                                }
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary
                        )
                    }
                }
            }

            if (nextDay.second.size > 3) {
                Spacer(modifier = Modifier.height(spacing.sm))
                Text(
                    text = "+${nextDay.second.size - 3} more",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextTertiary,
                    textAlign = TextAlign.Center
                )
            }
        }

        if (nextDay == null && viewModel.uiState.value.allSchedules.isEmpty()) {
            Spacer(modifier = Modifier.height(spacing.sm))
            Text(
                text = "You haven't been enrolled in any classes yet",
                style = MaterialTheme.typography.bodyMedium,
                color = TextTertiary,
                textAlign = TextAlign.Center
            )
        }
    }
}

// ── Activity Feed Item ──

@Composable
private fun ActivityFeedItem(
    record: AttendanceRecordResponse,
    viewModel: StudentHomeViewModel
) {
    val spacing = IAMSThemeTokens.spacing
    val (subjectName, _) = viewModel.getScheduleInfoForRecord(record)
    val status = parseAttendanceStatus(record.status)

    IAMSCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = subjectName,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = Primary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Spacer(modifier = Modifier.height(spacing.xs))
                Text(
                    text = formatDateDisplay(record.date),
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
            }
            Spacer(modifier = Modifier.width(spacing.sm))
            IAMSBadge(status = status)
        }
    }
}

// ── Utility functions ──

private fun formatDateDisplay(date: String): String {
    return try {
        val localDate = LocalDate.parse(date)
        localDate.format(DateTimeFormatter.ofPattern("MMM dd, yyyy", Locale.getDefault()))
    } catch (_: Exception) {
        date
    }
}

private fun getDayName(backendDay: Int): String {
    val days = listOf("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    return days.getOrElse(backendDay) { "" }
}

@Composable
private fun RealtimeConnectionBanner(
    health: com.iams.app.data.model.RealtimeConnectionHealth,
) {
    if (health == com.iams.app.data.model.RealtimeConnectionHealth.CONNECTED) return
    val spacing = IAMSThemeTokens.spacing
    val (text, bg, fg) = when (health) {
        com.iams.app.data.model.RealtimeConnectionHealth.RECONNECTING ->
            Triple("Reconnecting\u2026", LateBg, LateFg)
        com.iams.app.data.model.RealtimeConnectionHealth.OFFLINE ->
            Triple("Offline \u2014 updates paused", AbsentBg, AbsentFg)
        else -> Triple("", Background, TextSecondary)
    }
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = spacing.sm),
        color = bg,
        shape = IAMSThemeTokens.radius.mdShape,
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = spacing.md, vertical = spacing.xs),
            style = MaterialTheme.typography.bodySmall,
            color = fg,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

