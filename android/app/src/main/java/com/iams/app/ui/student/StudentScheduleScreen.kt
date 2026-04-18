package com.iams.app.ui.student

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.ScheduleResponse
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.components.NotificationBellButton
import com.iams.app.ui.components.SkeletonBox
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.PrimaryForeground
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import java.time.LocalDate

private val DAYS = listOf(0, 1, 2, 3, 4, 5, 6) // 0=Monday .. 6=Sunday

private val SHORT_DAY_NAMES = listOf("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")

private val FULL_DAY_NAMES = listOf(
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudentScheduleScreen(
    navController: NavController,
    viewModel: StudentScheduleViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val todayStatusByScheduleId by viewModel.todayStatusByScheduleId.collectAsState()
    val spacing = IAMSThemeTokens.spacing
    val toastState = LocalToastState.current

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            toastState.showToast(it, ToastType.ERROR)
            viewModel.clearError()
        }
    }

    // Error state (no cached data)
    if (uiState.error != null && uiState.allSchedules.isEmpty() && !uiState.isLoading) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(Background)
        ) {
            IAMSHeader(
                title = "Schedule",
                trailing = {
                    NotificationBellButton(
                        notificationService = viewModel.notificationService,
                        onClick = { navController.navigate(Routes.STUDENT_NOTIFICATIONS) },
                    )
                },
            )

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
                        text = "Unable to load schedule. Please try again.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextSecondary,
                        textAlign = TextAlign.Center
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                    IAMSButton(
                        text = "Retry",
                        onClick = {
                            viewModel.clearError()
                            viewModel.loadSchedules()
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

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        IAMSHeader(
                title = "Schedule",
                trailing = {
                    NotificationBellButton(
                        notificationService = viewModel.notificationService,
                        onClick = { navController.navigate(Routes.STUDENT_NOTIFICATIONS) },
                    )
                },
            )

        // Day selector
        val todayBackend = LocalDate.now().dayOfWeek.value - 1

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = spacing.lg, vertical = spacing.lg),
            horizontalArrangement = Arrangement.spacedBy(spacing.xs),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            DAYS.forEach { day ->
                DayPill(
                    label = SHORT_DAY_NAMES[day],
                    isSelected = day == uiState.selectedDay,
                    isToday = day == todayBackend,
                    onClick = { viewModel.selectDay(day) },
                    modifier = Modifier.weight(1f),
                )
            }
        }

        HorizontalDivider(thickness = 1.dp, color = Border)

        // Schedule list with pull-to-refresh
        val daySchedules = viewModel.getSelectedDaySchedules()

        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize()
        ) {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = spacing.lg),
            ) {
                item { Spacer(modifier = Modifier.height(spacing.lg)) }

                if (uiState.isLoading && daySchedules.isEmpty()) {
                    items(3) {
                        IAMSCard {
                            Column(modifier = Modifier.fillMaxWidth()) {
                                SkeletonBox(width = 80.dp, height = 14.dp)
                                Spacer(modifier = Modifier.height(4.dp))
                                SkeletonBox(width = 200.dp, height = 18.dp)
                                Spacer(modifier = Modifier.height(4.dp))
                                SkeletonBox(width = 100.dp, height = 12.dp)
                                Spacer(modifier = Modifier.height(8.dp))
                                SkeletonBox(width = 180.dp, height = 14.dp)
                                Spacer(modifier = Modifier.height(4.dp))
                                SkeletonBox(width = 120.dp, height = 12.dp)
                            }
                        }
                        Spacer(modifier = Modifier.height(spacing.sm))
                    }
                } else if (daySchedules.isNotEmpty()) {
                    // Only show today's live status; other days should fall
                    // back to stored history (future UX enhancement) rather
                    // than misrepresent a different day's status as today's.
                    val showLiveStatus = uiState.selectedDay == (LocalDate.now().dayOfWeek.value - 1)
                    items(daySchedules, key = { it.id }) { schedule ->
                        ScheduleCard(
                            schedule = schedule,
                            liveStatus = if (showLiveStatus) todayStatusByScheduleId[schedule.id] else null,
                        )
                        Spacer(modifier = Modifier.height(spacing.sm))
                    }
                } else if (!uiState.isLoading) {
                    item {
                        ScheduleEmptyState(selectedDay = uiState.selectedDay)
                    }
                }

                item { Spacer(modifier = Modifier.height(spacing.lg)) }
            }
        }
    }
}

@Composable
private fun DayPill(
    label: String,
    isSelected: Boolean,
    isToday: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        contentAlignment = Alignment.Center,
        modifier = modifier
            .height(40.dp)
            .clip(RoundedCornerShape(9999.dp))
            .background(if (isSelected) Primary else Secondary)
            .clickable(onClick = onClick),
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
            color = if (isSelected) PrimaryForeground else TextSecondary,
            maxLines = 1,
            overflow = TextOverflow.Clip,
            textAlign = TextAlign.Center,
        )
        // Today indicator dot at the bottom of the pill
        if (isToday && !isSelected) {
            Box(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 4.dp)
                    .size(4.dp)
                    .clip(CircleShape)
                    .background(Primary)
            )
        }
    }
}

@Composable
private fun ScheduleCard(
    schedule: ScheduleResponse,
    liveStatus: String? = null,
) {
    val spacing = IAMSThemeTokens.spacing

    IAMSCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            // Row 1: start time (bold) + today's status chip on the right
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = formatTimeDisplay(schedule.startTime),
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Bold,
                    color = Primary
                )
                if (liveStatus != null) {
                    com.iams.app.ui.components.IAMSBadge(
                        status = com.iams.app.ui.utils.parseAttendanceStatus(liveStatus),
                    )
                }
            }

            Spacer(modifier = Modifier.height(spacing.xs))

            // Subject name
            Text(
                text = schedule.subjectName,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.SemiBold,
                color = Primary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )

            // Subject code
            if (!schedule.subjectCode.isNullOrBlank()) {
                Text(
                    text = schedule.subjectCode,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextTertiary
                )
            }

            Spacer(modifier = Modifier.height(spacing.sm))

            // Time range + room
            Text(
                text = buildString {
                    append(formatTimeDisplay(schedule.startTime))
                    append(" - ")
                    append(formatTimeDisplay(schedule.endTime))
                    if (!schedule.roomName.isNullOrBlank()) {
                        append(" \u2022 ")
                        append(schedule.roomName)
                    }
                },
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary
            )

            // Faculty name
            if (!schedule.facultyName.isNullOrBlank()) {
                Text(
                    text = schedule.facultyName,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextTertiary
                )
            }
        }
    }
}

@Composable
private fun ScheduleEmptyState(selectedDay: Int) {
    val spacing = IAMSThemeTokens.spacing
    val dayName = FULL_DAY_NAMES.getOrElse(selectedDay) { "" }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "You haven't been enrolled in any classes yet",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(spacing.sm))
        Text(
            text = "No classes scheduled for $dayName",
            style = MaterialTheme.typography.bodyMedium,
            color = TextTertiary,
            textAlign = TextAlign.Center
        )
    }
}

/**
 * Format "HH:MM:SS" or "HH:MM" to "h:mm AM/PM"
 */
private fun formatTimeDisplay(time: String): String {
    return try {
        val parts = time.split(":")
        val hours = parts[0].toInt()
        val minutes = parts[1].toInt()
        val period = if (hours >= 12) "PM" else "AM"
        val displayHours = if (hours % 12 == 0) 12 else hours % 12
        val displayMinutes = minutes.toString().padStart(2, '0')
        "$displayHours:$displayMinutes $period"
    } catch (_: Exception) {
        time
    }
}
