package com.iams.app.ui.faculty

import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
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
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.ui.graphics.Color
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material.icons.outlined.MenuBook
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.LiveAttendanceResponse
import com.iams.app.data.model.ScheduleResponse
import com.iams.app.ui.components.CardSkeleton
import com.iams.app.ui.components.SkeletonBox
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.PresentBorder
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultyHomeScreen(
    navController: NavController,
    viewModel: FacultyHomeViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val notifUnreadCount by viewModel.notificationService.unreadCount.collectAsState()
    val spacing = IAMSThemeTokens.spacing
    val toastState = LocalToastState.current

    // Show session messages as toasts
    LaunchedEffect(uiState.sessionMessage) {
        uiState.sessionMessage?.let { msg ->
            toastState.showToast(msg, ToastType.INFO)
            viewModel.clearSessionMessage()
        }
    }

    val currentClass = viewModel.getCurrentClass()
    val sessionActive = currentClass?.let { viewModel.isSessionActive(it.id) } ?: false
    val otherSchedules = uiState.todaySchedules.filter { it.id != currentClass?.id }

    var showEndDialog by remember { mutableStateOf(false) }

    // Manage polling lifecycle from the composable
    LaunchedEffect(sessionActive, currentClass?.id) {
        if (sessionActive && currentClass != null) {
            viewModel.startLiveAttendancePolling(currentClass.id)
        } else {
            viewModel.stopLiveAttendancePolling()
        }
    }

    if (showEndDialog && currentClass != null) {
        AlertDialog(
            onDismissRequest = { showEndDialog = false },
            title = { Text("End Class Session?") },
            text = { Text("This will stop attendance tracking for this class.") },
            confirmButton = {
                TextButton(onClick = {
                    showEndDialog = false
                    viewModel.endSession(currentClass.id)
                }) {
                    Text("End Session")
                }
            },
            dismissButton = {
                TextButton(onClick = { showEndDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize()
        ) {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(0.dp)
            ) {
                // Greeting + notification bell + Date
                item {
                    Spacer(modifier = Modifier.height(spacing.lg))

                    val fullName = uiState.user?.let {
                        "${it.firstName} ${it.lastName}"
                    } ?: "Faculty"

                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = spacing.screenPadding),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "${viewModel.getGreeting()}, $fullName!",
                            style = MaterialTheme.typography.headlineLarge,
                            fontWeight = FontWeight.Bold,
                            color = Primary,
                            modifier = Modifier.weight(1f)
                        )
                        IconButton(onClick = { navController.navigate(Routes.FACULTY_NOTIFICATIONS) }) {
                            BadgedBox(
                                badge = {
                                    val count = notifUnreadCount
                                    if (count > 0) {
                                        Badge(
                                            containerColor = Color(0xFFDC2626),
                                            contentColor = Color.White
                                        ) {
                                            Text(
                                                text = if (count > 99) "99+" else count.toString(),
                                                style = MaterialTheme.typography.labelSmall
                                            )
                                        }
                                    }
                                }
                            ) {
                                Icon(
                                    Icons.Outlined.Notifications,
                                    contentDescription = "Notifications",
                                    modifier = Modifier.size(24.dp),
                                    tint = TextPrimary
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(spacing.sm))

                    Text(
                        text = LocalDate.now().format(
                            DateTimeFormatter.ofPattern(
                                "EEEE, MMMM d, yyyy",
                                Locale.ENGLISH
                            )
                        ),
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextSecondary,
                        modifier = Modifier.padding(horizontal = spacing.screenPadding)
                    )
                }

                // Skeleton loader for current class area
                if (!uiState.initialLoadDone) {
                    item {
                        Spacer(modifier = Modifier.height(spacing.xxl))
                        IAMSCard(modifier = Modifier.padding(horizontal = spacing.screenPadding)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                SkeletonBox(width = 8.dp, height = 8.dp, cornerRadius = 4.dp)
                                Spacer(modifier = Modifier.width(spacing.sm))
                                SkeletonBox(width = 100.dp, height = 12.dp)
                            }
                            Spacer(modifier = Modifier.height(spacing.md))
                            SkeletonBox(width = 200.dp, height = 22.dp)
                            Spacer(modifier = Modifier.height(spacing.xs))
                            SkeletonBox(width = 240.dp, height = 14.dp)
                            Spacer(modifier = Modifier.height(spacing.lg))
                            SkeletonBox(height = 40.dp, cornerRadius = 8.dp)
                        }
                    }
                }

                // Current Class Hero / Inactive Card
                if (uiState.initialLoadDone && currentClass != null) {
                    item {
                        Spacer(modifier = Modifier.height(spacing.xxl))
                        if (sessionActive) {
                            ActiveSessionHeroCard(
                                schedule = currentClass,
                                liveAttendance = uiState.liveAttendance,
                                elapsedMinutes = viewModel.getElapsedMinutes(currentClass),
                                sessionLoading = uiState.sessionLoading,
                                onEndSession = { showEndDialog = true },
                                onViewCameraFeed = {
                                    val roomId = currentClass.roomId ?: return@ActiveSessionHeroCard
                                    navController.navigate(
                                        Routes.facultyLiveFeed(currentClass.id, roomId)
                                    )
                                },
                                formatTime = { viewModel.formatTime(it) },
                                modifier = Modifier.padding(horizontal = spacing.screenPadding)
                            )
                        } else {
                            InactiveCurrentClassCard(
                                schedule = currentClass,
                                sessionLoading = uiState.sessionLoading,
                                onStartSession = { viewModel.startSession(currentClass.id) },
                                formatTime = { viewModel.formatTime(it) },
                                modifier = Modifier.padding(horizontal = spacing.screenPadding)
                            )
                        }
                    }
                }

                // Section title: "Today's Classes"
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    Text(
                        text = if (uiState.initialLoadDone)
                            "Today's Classes (${uiState.todaySchedules.size})"
                        else
                            "Today's Classes",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = TextPrimary,
                        modifier = Modifier.padding(
                            horizontal = spacing.screenPadding,
                            vertical = 0.dp
                        )
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                }

                // Skeleton loaders for schedule list
                if (!uiState.initialLoadDone) {
                    items(2) {
                        CardSkeleton(modifier = Modifier.padding(horizontal = spacing.screenPadding))
                        Spacer(modifier = Modifier.height(spacing.sm))
                    }
                }

                // Today's schedule cards or empty state
                if (uiState.initialLoadDone && uiState.todaySchedules.isEmpty()) {
                    item {
                        EmptyScheduleState(
                            totalSchedules = uiState.allSchedules.size,
                            modifier = Modifier.padding(horizontal = spacing.screenPadding)
                        )
                    }
                } else if (uiState.initialLoadDone && otherSchedules.isEmpty() && currentClass != null) {
                    item {
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
                } else if (uiState.initialLoadDone) {
                    items(otherSchedules) { schedule ->
                        TodayScheduleCard(
                            schedule = schedule,
                            timeState = viewModel.getScheduleTimeState(schedule),
                            minutesUntilStart = viewModel.getMinutesUntilStart(schedule),
                            formatTime = { viewModel.formatTime(it) },
                            modifier = Modifier.padding(
                                horizontal = spacing.screenPadding,
                                vertical = 0.dp
                            )
                        )
                        Spacer(modifier = Modifier.height(spacing.sm))
                    }
                }

                // Day summary row
                if (uiState.initialLoadDone && uiState.todaySchedules.isNotEmpty()) {
                    item {
                        Spacer(modifier = Modifier.height(spacing.lg))
                        DaySummaryRow(
                            totalClasses = uiState.todaySchedules.size,
                            nextUpcoming = otherSchedules.firstOrNull {
                                viewModel.getScheduleTimeState(it) == ScheduleTimeState.UPCOMING
                            },
                            formatTime = { viewModel.formatTime(it) },
                            modifier = Modifier.padding(horizontal = spacing.screenPadding)
                        )
                    }
                }

                // Bottom spacing for nav bar
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                }
            }
        }
    }
}

@Composable
private fun ActiveSessionHeroCard(
    schedule: ScheduleResponse,
    liveAttendance: LiveAttendanceResponse?,
    elapsedMinutes: Long,
    sessionLoading: Boolean,
    onEndSession: () -> Unit,
    onViewCameraFeed: () -> Unit,
    formatTime: (String) -> String,
    modifier: Modifier = Modifier
) {
    val spacing = IAMSThemeTokens.spacing
    val radius = IAMSThemeTokens.radius

    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = radius.cardShape,
        color = Background,
        border = BorderStroke(1.5.dp, PresentBorder),
        shadowElevation = 0.dp,
    ) {
        Column(modifier = Modifier.padding(spacing.cardPadding)) {
            // Status row: green dot + label + elapsed time
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(10.dp)
                            .clip(CircleShape)
                            .background(PresentFg)
                    )
                    Spacer(modifier = Modifier.width(spacing.sm))
                    Text(
                        text = "SESSION ACTIVE",
                        style = MaterialTheme.typography.bodySmall.copy(
                            letterSpacing = 0.5.sp
                        ),
                        fontWeight = FontWeight.SemiBold,
                        color = PresentFg
                    )
                }
                Text(
                    text = "${elapsedMinutes} min elapsed",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextTertiary
                )
            }

            Spacer(modifier = Modifier.height(spacing.md))

            // Subject name
            Text(
                text = schedule.subjectName,
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )

            Spacer(modifier = Modifier.height(spacing.xs))

            // Room + Time
            Text(
                text = "${schedule.roomName ?: "No room"} \u2022 ${formatTime(schedule.startTime)} - ${formatTime(schedule.endTime)}",
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary
            )

            Spacer(modifier = Modifier.height(spacing.lg))

            // Stats row: Present / Absent / Late — consistent height
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(spacing.sm)
            ) {
                val totalEnrolled = liveAttendance?.totalEnrolled
                StatBox(
                    count = liveAttendance?.presentCount,
                    subtitle = if (totalEnrolled != null) "/$totalEnrolled" else null,
                    label = "Present",
                    color = PresentFg,
                    modifier = Modifier.weight(1f)
                )
                StatBox(
                    count = liveAttendance?.absentCount,
                    subtitle = null,
                    label = "Absent",
                    color = AbsentFg,
                    modifier = Modifier.weight(1f)
                )
                StatBox(
                    count = liveAttendance?.lateCount,
                    subtitle = null,
                    label = "Late",
                    color = LateFg,
                    modifier = Modifier.weight(1f)
                )
            }

            Spacer(modifier = Modifier.height(spacing.lg))

            // Action buttons: Camera Feed (primary) + End Class (secondary)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(spacing.sm)
            ) {
                IAMSButton(
                    text = "Open Camera Feed",
                    onClick = onViewCameraFeed,
                    variant = IAMSButtonVariant.PRIMARY,
                    size = IAMSButtonSize.MD,
                    modifier = Modifier.weight(1f),
                    leadingIcon = {
                        Icon(
                            Icons.Default.Videocam,
                            contentDescription = null,
                            modifier = Modifier.size(16.dp),
                            tint = Background
                        )
                    }
                )
                IAMSButton(
                    text = "End Class",
                    onClick = onEndSession,
                    variant = IAMSButtonVariant.SECONDARY,
                    size = IAMSButtonSize.MD,
                    fullWidth = false,
                    enabled = !sessionLoading,
                    isLoading = sessionLoading,
                    loadingText = "Ending...",
                    leadingIcon = {
                        Icon(
                            Icons.Default.Stop,
                            contentDescription = null,
                            modifier = Modifier.size(16.dp),
                            tint = TextPrimary
                        )
                    }
                )
            }
        }
    }
}

@Composable
private fun StatBox(
    count: Int?,
    subtitle: String?,
    label: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    val spacing = IAMSThemeTokens.spacing
    val radius = IAMSThemeTokens.radius

    Surface(
        modifier = modifier,
        shape = radius.smShape,
        color = Secondary,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = spacing.md, vertical = spacing.md),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = count?.toString() ?: "\u2014",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = color
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = label,
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
            // Always render subtitle line for consistent height
            Text(
                text = subtitle ?: "",
                style = MaterialTheme.typography.bodySmall,
                color = TextTertiary
            )
        }
    }
}

@Composable
private fun InactiveCurrentClassCard(
    schedule: ScheduleResponse,
    sessionLoading: Boolean,
    onStartSession: () -> Unit,
    formatTime: (String) -> String,
    modifier: Modifier = Modifier
) {
    val spacing = IAMSThemeTokens.spacing

    IAMSCard(modifier = modifier) {
        // Status row
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(TextTertiary)
            )
            Spacer(modifier = Modifier.width(spacing.sm))
            Text(
                text = "CURRENT CLASS",
                style = MaterialTheme.typography.bodySmall.copy(
                    letterSpacing = 0.5.sp
                ),
                fontWeight = FontWeight.Medium,
                color = TextTertiary
            )
        }

        Spacer(modifier = Modifier.height(spacing.md))

        // Subject name
        Text(
            text = schedule.subjectName,
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.SemiBold,
            color = TextPrimary
        )

        Spacer(modifier = Modifier.height(spacing.xs))

        // Room + Time
        Text(
            text = "${schedule.roomName ?: "No room"} \u2022 ${formatTime(schedule.startTime)} - ${formatTime(schedule.endTime)}",
            style = MaterialTheme.typography.bodyMedium,
            color = TextSecondary
        )

        Spacer(modifier = Modifier.height(spacing.lg))

        // Start Class button
        IAMSButton(
            text = "Start Class",
            onClick = onStartSession,
            variant = IAMSButtonVariant.PRIMARY,
            size = IAMSButtonSize.MD,
            fullWidth = true,
            enabled = !sessionLoading,
            isLoading = sessionLoading,
            loadingText = "Starting...",
            leadingIcon = {
                Icon(
                    Icons.Default.PlayArrow,
                    contentDescription = null,
                    modifier = Modifier.size(16.dp),
                    tint = Background
                )
            }
        )
    }
}

@Composable
private fun TodayScheduleCard(
    schedule: ScheduleResponse,
    timeState: ScheduleTimeState,
    minutesUntilStart: Long,
    formatTime: (String) -> String,
    modifier: Modifier = Modifier
) {
    val spacing = IAMSThemeTokens.spacing

    IAMSCard(modifier = modifier) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top
        ) {
            // Left: schedule info
            Column(modifier = Modifier.weight(1f)) {
                // Time range
                Text(
                    text = "${formatTime(schedule.startTime)} - ${formatTime(schedule.endTime)}",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary
                )

                Spacer(modifier = Modifier.height(spacing.xs))

                // Subject name
                Text(
                    text = schedule.subjectName,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = TextPrimary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )

                Spacer(modifier = Modifier.height(spacing.xs))

                // Room
                Text(
                    text = schedule.roomName ?: "",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
            }

            // Right: time state badge
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

@Composable
private fun DaySummaryRow(
    totalClasses: Int,
    nextUpcoming: ScheduleResponse?,
    formatTime: (String) -> String,
    modifier: Modifier = Modifier
) {
    val spacing = IAMSThemeTokens.spacing

    Row(
        modifier = modifier
            .fillMaxWidth()
            .height(IntrinsicSize.Min),
        horizontalArrangement = Arrangement.spacedBy(spacing.sm)
    ) {
        // Total classes card
        IAMSCard(modifier = Modifier.weight(1f).fillMaxHeight()) {
            Text(
                text = totalClasses.toString(),
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
            Spacer(modifier = Modifier.height(spacing.xs))
            Text(
                text = "Classes today",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }

        // Next class or all done
        IAMSCard(modifier = Modifier.weight(1f).fillMaxHeight()) {
            if (nextUpcoming != null) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Outlined.Schedule,
                        contentDescription = null,
                        modifier = Modifier.size(14.dp),
                        tint = TextTertiary
                    )
                    Spacer(modifier = Modifier.width(spacing.xs))
                    Text(
                        text = "Next",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextTertiary
                    )
                }
                Spacer(modifier = Modifier.height(spacing.xs))
                Text(
                    text = formatTime(nextUpcoming.startTime),
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary
                )
                Text(
                    text = nextUpcoming.subjectName,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            } else {
                Text(
                    text = "All done",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary
                )
                Spacer(modifier = Modifier.height(spacing.xs))
                Text(
                    text = "No more classes today",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
            }
        }
    }
}

@Composable
private fun EmptyScheduleState(
    totalSchedules: Int,
    modifier: Modifier = Modifier
) {
    val spacing = IAMSThemeTokens.spacing

    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = spacing.xxxl),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Icon circle
        Box(
            modifier = Modifier
                .size(80.dp)
                .clip(CircleShape)
                .background(Secondary),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = if (totalSchedules == 0) Icons.Outlined.MenuBook
                else Icons.Outlined.CalendarMonth,
                contentDescription = null,
                modifier = Modifier.size(48.dp),
                tint = TextTertiary
            )
        }

        Spacer(modifier = Modifier.height(spacing.lg))

        Text(
            text = if (totalSchedules == 0) "No Classes Assigned" else "No classes today",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
            color = TextPrimary
        )

        Spacer(modifier = Modifier.height(spacing.sm))

        Text(
            text = if (totalSchedules == 0)
                "You don't have any classes assigned yet.\nContact your administrator to set up your schedule."
            else
                "You have no classes scheduled for today. Enjoy your free day!",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(horizontal = spacing.lg)
        )
    }
}
