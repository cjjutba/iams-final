package com.iams.app.ui.faculty

import androidx.compose.foundation.background
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccessTime
import androidx.compose.material.icons.filled.CalendarToday
import androidx.compose.material.icons.filled.MeetingRoom
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
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
import com.iams.app.data.model.AttendanceSummaryResponse
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.EarlyLeaveFg
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultyReportsScreen(
    navController: NavController,
    viewModel: FacultyReportsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    PullToRefreshBox(
        isRefreshing = uiState.isRefreshing,
        onRefresh = { viewModel.refresh() },
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        when {
            uiState.isLoading && uiState.schedules.isEmpty() -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(color = Primary)
                }
            }

            uiState.error != null && uiState.schedules.isEmpty() -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = uiState.error!!,
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.error,
                            textAlign = TextAlign.Center
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        IAMSButton(
                            text = "Retry",
                            onClick = { viewModel.loadData() },
                            variant = IAMSButtonVariant.OUTLINE,
                            fullWidth = false
                        )
                    }
                }
            }

            else -> {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    item {
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            text = "Attendance Reports",
                            style = MaterialTheme.typography.headlineLarge,
                            fontWeight = FontWeight.Bold,
                            color = Primary
                        )
                    }

                    if (uiState.schedules.isEmpty()) {
                        item {
                            IAMSCard {
                                Text(
                                    text = "No classes assigned",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = TextSecondary,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(12.dp),
                                    textAlign = TextAlign.Center
                                )
                            }
                        }
                    } else {
                        items(uiState.schedules) { item ->
                            ScheduleReportCard(item)
                        }
                    }

                    // Bottom spacing for nav bar
                    item {
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun ScheduleReportCard(item: ScheduleWithSummary) {
    val schedule = item.schedule
    val summary = item.summary

    IAMSCard {
        // Subject name
        Text(
            text = schedule.subjectName,
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.SemiBold,
            color = Primary
        )

        if (schedule.subjectCode != null) {
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = schedule.subjectCode,
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Schedule details
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                Icons.Default.CalendarToday,
                contentDescription = "Day",
                modifier = Modifier.size(14.dp),
                tint = TextSecondary
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = schedule.dayOfWeek,
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
            Spacer(modifier = Modifier.width(16.dp))
            Icon(
                Icons.Default.AccessTime,
                contentDescription = "Time",
                modifier = Modifier.size(14.dp),
                tint = TextSecondary
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = "${schedule.startTime} - ${schedule.endTime}",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }

        if (schedule.roomName != null) {
            Spacer(modifier = Modifier.height(4.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    Icons.Default.MeetingRoom,
                    contentDescription = "Room",
                    modifier = Modifier.size(14.dp),
                    tint = TextSecondary
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = schedule.roomName,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
            }
        }

        Spacer(modifier = Modifier.height(12.dp))
        HorizontalDivider(color = Border, thickness = 1.dp)
        Spacer(modifier = Modifier.height(12.dp))

        // Attendance summary
        if (item.isLoadingSummary) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 8.dp),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    strokeWidth = 2.dp,
                    color = Primary
                )
            }
        } else if (summary != null) {
            AttendanceSummaryContent(summary)
        } else {
            Text(
                text = "No attendance data available",
                style = MaterialTheme.typography.bodySmall,
                color = TextTertiary,
                modifier = Modifier.fillMaxWidth(),
                textAlign = TextAlign.Center
            )
        }
    }
}

@Composable
private fun AttendanceSummaryContent(summary: AttendanceSummaryResponse) {
    val ratePercent = (summary.attendanceRate * 100).toInt()
    val rateColor = when {
        ratePercent >= 80 -> PresentFg
        ratePercent >= 60 -> LateFg
        else -> AbsentFg
    }

    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Attendance Rate",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                color = Primary
            )
            Text(
                text = "$ratePercent%",
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold,
                color = rateColor
            )
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Attendance bar with colored segments
        AttendanceBar(summary)

        Spacer(modifier = Modifier.height(12.dp))

        // Stats row
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly
        ) {
            StatItem(label = "Total", value = "${summary.totalClasses}", color = Primary)
            StatItem(label = "Present", value = "${summary.presentCount}", color = PresentFg)
            StatItem(label = "Late", value = "${summary.lateCount}", color = LateFg)
            StatItem(label = "Absent", value = "${summary.absentCount}", color = AbsentFg)
        }
    }
}

@Composable
private fun AttendanceBar(summary: AttendanceSummaryResponse) {
    val total = summary.totalClasses.coerceAtLeast(1).toFloat()
    val presentFraction = summary.presentCount / total
    val lateFraction = summary.lateCount / total
    val absentFraction = summary.absentCount / total
    // Early leave gets the remainder
    val earlyLeaveFraction = (1f - presentFraction - lateFraction - absentFraction).coerceAtLeast(0f)

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(12.dp)
            .clip(RoundedCornerShape(6.dp))
            .background(Secondary)
    ) {
        if (presentFraction > 0f) {
            Box(
                modifier = Modifier
                    .weight(presentFraction)
                    .height(12.dp)
                    .background(PresentFg)
            )
        }
        if (lateFraction > 0f) {
            Box(
                modifier = Modifier
                    .weight(lateFraction)
                    .height(12.dp)
                    .background(LateFg)
            )
        }
        if (earlyLeaveFraction > 0f) {
            Box(
                modifier = Modifier
                    .weight(earlyLeaveFraction)
                    .height(12.dp)
                    .background(EarlyLeaveFg)
            )
        }
        if (absentFraction > 0f) {
            Box(
                modifier = Modifier
                    .weight(absentFraction)
                    .height(12.dp)
                    .background(AbsentFg)
            )
        }
    }
}

@Composable
private fun StatItem(
    label: String,
    value: String,
    color: androidx.compose.ui.graphics.Color
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = value,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = color
        )
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary
        )
    }
}
