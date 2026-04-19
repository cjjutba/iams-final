package com.iams.app.ui.faculty

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.ScheduleResponse
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.components.NotificationBellButton
import com.iams.app.ui.components.SkeletonBox
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.PrimaryForeground
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

private val DAY_LABELS = listOf("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultyScheduleScreen(
    navController: NavController,
    viewModel: FacultyScheduleViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing
    val filteredSchedules = viewModel.filteredSchedules()
    val todayDay = viewModel.todayScheduleDay()

    Column(modifier = Modifier.fillMaxSize()) {
        IAMSHeader(
            title = "Schedule",
            trailing = {
                NotificationBellButton(
                    notificationService = viewModel.notificationService,
                    onClick = { navController.navigate(Routes.FACULTY_NOTIFICATIONS) },
                )
            },
        )

        // Day selector — horizontally scrollable pill row.
        // Pills keep their intrinsic width so longer labels never get clipped
        // and narrow phones can swipe to reach the last day.
        val dayListState = rememberLazyListState()
        LaunchedEffect(uiState.selectedDay) {
            // Center the selected day so today/Sun/Sat are never hidden behind
            // the screen edge after the user (or the VM) flips selection.
            dayListState.animateScrollToItem(uiState.selectedDay)
        }

        LazyRow(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = spacing.lg),
            state = dayListState,
            contentPadding = PaddingValues(horizontal = spacing.lg),
            horizontalArrangement = Arrangement.spacedBy(spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            itemsIndexed(DAY_LABELS) { index, label ->
                DayButton(
                    label = label,
                    isSelected = index == uiState.selectedDay,
                    isToday = index == todayDay,
                    onClick = { viewModel.selectDay(index) }
                )
            }
        }

        HorizontalDivider(thickness = 1.dp, color = Border)

        // Schedule list
        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize(),
        ) {
            LazyColumn(
                contentPadding = PaddingValues(spacing.lg),
                verticalArrangement = Arrangement.spacedBy(spacing.sm),
                modifier = Modifier.fillMaxSize(),
            ) {
                if (uiState.isLoading && filteredSchedules.isEmpty()) {
                    items(3) {
                        IAMSCard {
                            SkeletonBox(width = 180.dp, height = 20.dp)
                            Spacer(modifier = Modifier.height(spacing.xs))
                            SkeletonBox(width = 100.dp, height = 12.dp)
                            Spacer(modifier = Modifier.height(spacing.sm))
                            SkeletonBox(width = 140.dp, height = 12.dp)
                            Spacer(modifier = Modifier.height(spacing.xs))
                            SkeletonBox(width = 80.dp, height = 12.dp)
                        }
                    }
                } else if (filteredSchedules.isEmpty() && !uiState.isLoading) {
                    item {
                        ScheduleEmptyState(
                            dayName = getDayName(uiState.selectedDay)
                        )
                    }
                } else {
                    items(filteredSchedules, key = { it.id }) { schedule ->
                        ScheduleCard(
                            schedule = schedule,
                            onClick = {
                                navController.navigate(
                                    "classDetail/${schedule.id}/${java.time.LocalDate.now()}"
                                )
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun DayButton(
    label: String,
    isSelected: Boolean,
    isToday: Boolean,
    onClick: () -> Unit,
) {
    val pillHeight = 40.dp
    val pillWidth = 56.dp

    Box(
        contentAlignment = Alignment.Center,
        modifier = Modifier
            .width(pillWidth)
            .height(pillHeight)
            .clip(RoundedCornerShape(9999.dp))
            .background(if (isSelected) Primary else Secondary)
            .clickable(onClick = onClick),
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
            color = if (isSelected) PrimaryForeground else TextSecondary,
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
    onClick: () -> Unit,
) {
    val spacing = IAMSThemeTokens.spacing

    IAMSCard(onClick = onClick) {
        Text(
            text = schedule.subjectName,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
        )
        if (!schedule.subjectCode.isNullOrBlank()) {
            Spacer(modifier = Modifier.height(spacing.xs))
            Text(
                text = schedule.subjectCode,
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary,
            )
        }
        Spacer(modifier = Modifier.height(spacing.sm))
        Text(
            text = "${schedule.startTime} - ${schedule.endTime}",
            style = MaterialTheme.typography.bodySmall,
            color = TextTertiary,
        )
        if (!schedule.roomName.isNullOrBlank()) {
            Spacer(modifier = Modifier.height(spacing.xs))
            Text(
                text = schedule.roomName,
                style = MaterialTheme.typography.bodySmall,
                color = TextTertiary,
            )
        }
    }
}

@Composable
private fun ScheduleEmptyState(dayName: String) {
    val spacing = IAMSThemeTokens.spacing

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = "No classes today",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = TextAlign.Center,
        )
        Spacer(modifier = Modifier.height(spacing.sm))
        Text(
            text = "No classes scheduled for $dayName",
            style = MaterialTheme.typography.bodySmall,
            color = TextTertiary,
            textAlign = TextAlign.Center,
        )
    }
}

private fun getDayName(day: Int): String = when (day) {
    0 -> "Monday"
    1 -> "Tuesday"
    2 -> "Wednesday"
    3 -> "Thursday"
    4 -> "Friday"
    5 -> "Saturday"
    6 -> "Sunday"
    else -> ""
}
