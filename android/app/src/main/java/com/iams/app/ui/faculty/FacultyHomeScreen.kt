package com.iams.app.ui.faculty

import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material.icons.outlined.MenuBook
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import com.iams.app.data.model.ScheduleResponse
import com.iams.app.ui.components.CardSkeleton
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Secondary
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

    var showEndDialog by remember { mutableStateOf(false) }

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
        // Header with notification bell
        IAMSHeader(
            title = "Home",
            trailing = {
                IconButton(onClick = { navController.navigate(Routes.FACULTY_NOTIFICATIONS) }) {
                    Icon(
                        Icons.Default.Notifications,
                        contentDescription = "Notifications",
                        modifier = Modifier.size(24.dp),
                        tint = TextPrimary
                    )
                }
            }
        )

        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize()
        ) {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(0.dp)
            ) {
                // Greeting + Date
                item {
                    Column(
                        modifier = Modifier.padding(
                            start = spacing.screenPadding,
                            end = spacing.screenPadding,
                            top = spacing.xxl
                        )
                    ) {
                        val fullName = uiState.user?.let {
                            "${it.firstName} ${it.lastName}"
                        } ?: "Faculty"

                        Text(
                            text = "${viewModel.getGreeting()}, $fullName!",
                            style = MaterialTheme.typography.headlineLarge,
                            fontWeight = FontWeight.Bold,
                            color = TextPrimary
                        )

                        Spacer(modifier = Modifier.height(spacing.sm))

                        Text(
                            text = LocalDate.now().format(
                                DateTimeFormatter.ofPattern(
                                    "EEEE, MMMM d, yyyy",
                                    Locale.ENGLISH
                                )
                            ),
                            style = MaterialTheme.typography.bodyLarge,
                            color = TextSecondary
                        )
                    }
                }

                // Skeleton loader for current class area
                if (!uiState.initialLoadDone) {
                    item {
                        Spacer(modifier = Modifier.height(spacing.xxl))
                        CardSkeleton(modifier = Modifier.padding(horizontal = spacing.screenPadding))
                    }
                }

                // Current Class Card
                if (uiState.initialLoadDone && currentClass != null) {
                    item {
                        Spacer(modifier = Modifier.height(spacing.xxl))
                        CurrentClassCard(
                            schedule = currentClass,
                            sessionActive = sessionActive,
                            sessionLoading = uiState.sessionLoading,
                            onStartSession = { viewModel.startSession(currentClass.id) },
                            onEndSession = { showEndDialog = true },
                            onViewAttendance = {
                                // Navigate to live attendance
                            },
                            onViewCameraFeed = {
                                val roomId = currentClass.roomId ?: return@CurrentClassCard
                                navController.navigate(
                                    Routes.facultyLiveFeed(currentClass.id, roomId)
                                )
                            },
                            formatTime = { viewModel.formatTime(it) },
                            modifier = Modifier.padding(horizontal = spacing.screenPadding)
                        )
                    }
                }

                // Section title: "Today's Classes"
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    Text(
                        text = "Today's Classes",
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
                    items(3) {
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
                } else if (uiState.initialLoadDone) {
                    items(uiState.todaySchedules) { schedule ->
                        TodayScheduleCard(
                            schedule = schedule,
                            formatTime = { viewModel.formatTime(it) },
                            modifier = Modifier.padding(
                                horizontal = spacing.screenPadding,
                                vertical = 0.dp
                            )
                        )
                        Spacer(modifier = Modifier.height(spacing.sm))
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
private fun CurrentClassCard(
    schedule: ScheduleResponse,
    sessionActive: Boolean,
    sessionLoading: Boolean,
    onStartSession: () -> Unit,
    onEndSession: () -> Unit,
    onViewAttendance: () -> Unit,
    onViewCameraFeed: () -> Unit,
    formatTime: (String) -> String,
    modifier: Modifier = Modifier
) {
    val spacing = IAMSThemeTokens.spacing

    IAMSCard(modifier = modifier) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            // Left: status + subject info
            Column(modifier = Modifier.weight(1f)) {
                // Session status row
                Row(
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(if (sessionActive) PresentFg else TextTertiary)
                    )
                    Spacer(modifier = Modifier.width(spacing.sm))
                    Text(
                        text = if (sessionActive) "SESSION ACTIVE" else "SESSION INACTIVE",
                        style = MaterialTheme.typography.bodySmall.copy(
                            letterSpacing = 0.5.sp
                        ),
                        fontWeight = FontWeight.Medium,
                        color = if (sessionActive) PresentFg else TextTertiary
                    )
                }

                Spacer(modifier = Modifier.height(spacing.sm))

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
            }

            // Right: View button
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier
                    .clickable(enabled = sessionActive) { onViewAttendance() }
                    .padding(horizontal = spacing.md)
            ) {
                Icon(
                    Icons.Default.Notifications,
                    contentDescription = "View Attendance",
                    modifier = Modifier.size(20.dp),
                    tint = if (sessionActive) TextSecondary else TextTertiary
                )
                Spacer(modifier = Modifier.height(spacing.xs))
                Text(
                    text = "View",
                    style = MaterialTheme.typography.bodySmall,
                    color = if (sessionActive) TextSecondary else TextTertiary
                )
            }
        }

        Spacer(modifier = Modifier.height(spacing.lg))

        // Session control buttons
        if (sessionActive) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(spacing.sm)
            ) {
                // End Class button
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

                // View Live Attendance button
                IAMSButton(
                    text = "View Live Attendance",
                    onClick = onViewAttendance,
                    variant = IAMSButtonVariant.PRIMARY,
                    size = IAMSButtonSize.MD,
                    modifier = Modifier.weight(1f)
                )
            }
        } else {
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

        // Camera feed link when session is active
        if (sessionActive) {
            HorizontalDivider(
                modifier = Modifier.padding(top = spacing.md),
                thickness = 1.dp,
                color = Border
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onViewCameraFeed() }
                    .padding(top = spacing.md),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    Icons.Default.Videocam,
                    contentDescription = null,
                    modifier = Modifier.size(14.dp),
                    tint = Primary
                )
                Spacer(modifier = Modifier.width(spacing.xs))
                Text(
                    text = "View Camera Feed",
                    style = MaterialTheme.typography.bodySmall,
                    color = Primary
                )
            }
        }
    }
}

@Composable
private fun TodayScheduleCard(
    schedule: ScheduleResponse,
    formatTime: (String) -> String,
    modifier: Modifier = Modifier
) {
    val spacing = IAMSThemeTokens.spacing

    IAMSCard(modifier = modifier) {
        // Time
        Text(
            text = "${formatTime(schedule.startTime)} - ${formatTime(schedule.endTime)}",
            style = MaterialTheme.typography.bodyLarge,
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

        // Subject code
        if (schedule.subjectCode != null) {
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = schedule.subjectCode,
                style = MaterialTheme.typography.bodySmall,
                color = TextTertiary
            )
        }

        Spacer(modifier = Modifier.height(spacing.sm))

        // Room + faculty
        Row(
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = schedule.roomName ?: "",
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary
            )
            if (schedule.facultyName != null) {
                Text(
                    text = " \u2022 ${schedule.facultyName}",
                    style = MaterialTheme.typography.bodyMedium,
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
