package com.iams.app.ui.student

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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AccessTime
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.TrendingUp
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
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
import com.iams.app.data.model.PresenceLogResponse
import com.iams.app.ui.components.AttendanceStatus
import com.iams.app.ui.components.CardSkeleton
import com.iams.app.ui.components.IAMSBadge
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.components.SkeletonBox
import com.iams.app.ui.components.TextSkeleton
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.PresentFg
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import java.time.LocalDate
import java.time.LocalTime
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudentAttendanceDetailScreen(
    navController: NavController,
    viewModel: StudentAttendanceDetailViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        // Loading state — skeleton loaders
        if (uiState.isLoading) {
            IAMSHeader(
                title = "Attendance Details",
                onBack = { navController.popBackStack() }
            )

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(spacing.screenPadding)
            ) {
                // Status badge skeleton
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = spacing.xxl),
                    contentAlignment = Alignment.Center
                ) {
                    SkeletonBox(width = 80.dp, height = 28.dp, cornerRadius = 14.dp)
                }
                // Stats row skeleton
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = spacing.lg),
                    horizontalArrangement = Arrangement.spacedBy(spacing.md)
                ) {
                    IAMSCard(modifier = Modifier.weight(1f)) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            SkeletonBox(width = 20.dp, height = 20.dp, cornerRadius = 4.dp)
                            Spacer(modifier = Modifier.height(spacing.sm))
                            TextSkeleton(width = 80.dp)
                            Spacer(modifier = Modifier.height(spacing.xs))
                            SkeletonBox(width = 60.dp, height = 20.dp)
                        }
                    }
                    IAMSCard(modifier = Modifier.weight(1f)) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            SkeletonBox(width = 20.dp, height = 20.dp, cornerRadius = 4.dp)
                            Spacer(modifier = Modifier.height(spacing.sm))
                            TextSkeleton(width = 80.dp)
                            Spacer(modifier = Modifier.height(spacing.xs))
                            SkeletonBox(width = 60.dp, height = 20.dp)
                        }
                    }
                }
                // Timeline skeleton
                HorizontalDivider(
                    modifier = Modifier.padding(vertical = spacing.xxl),
                    thickness = 1.dp,
                    color = Border
                )
                TextSkeleton(width = 140.dp, height = 18.dp)
                Spacer(modifier = Modifier.height(spacing.lg))
                repeat(3) {
                    CardSkeleton()
                    Spacer(modifier = Modifier.height(spacing.sm))
                }
            }
            return@Column
        }

        // Error state
        if (uiState.error != null) {
            IAMSHeader(
                title = "Attendance Details",
                onBack = { navController.popBackStack() }
            )

            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.padding(horizontal = spacing.xxl)
                ) {
                    Icon(
                        Icons.Outlined.Refresh,
                        contentDescription = null,
                        modifier = Modifier.size(40.dp),
                        tint = TextTertiary
                    )

                    Spacer(modifier = Modifier.height(spacing.lg))

                    Text(
                        text = "Unable to load attendance details. Please try again.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextSecondary,
                        textAlign = TextAlign.Center
                    )

                    Spacer(modifier = Modifier.height(spacing.lg))

                    IAMSButton(
                        text = "Retry",
                        onClick = { viewModel.loadDetails() },
                        variant = IAMSButtonVariant.SECONDARY,
                        size = IAMSButtonSize.MD,
                        fullWidth = false
                    )
                }
            }
            return@Column
        }

        // Empty state (no attendance record)
        val attendance = uiState.attendance
        if (attendance == null) {
            IAMSHeader(
                title = "Attendance Details",
                onBack = { navController.popBackStack() }
            )

            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.padding(horizontal = spacing.xxl)
                ) {
                    Text(
                        text = "No attendance record found",
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextSecondary,
                        textAlign = TextAlign.Center
                    )

                    Spacer(modifier = Modifier.height(spacing.sm))

                    Text(
                        text = "Attendance has not been recorded yet for this class",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextTertiary,
                        textAlign = TextAlign.Center
                    )
                }
            }
            return@Column
        }

        // Header with formatted date
        val headerTitle = formatDisplayDate(viewModel.getHeaderDate() ?: attendance.date)
        IAMSHeader(
            title = headerTitle,
            onBack = { navController.popBackStack() }
        )

        // Main content with pull-to-refresh
        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize()
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(spacing.screenPadding)
            ) {
                // Status badge - centered
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = spacing.xxl),
                    contentAlignment = Alignment.Center
                ) {
                    IAMSBadge(status = parseStatus(attendance.status))
                }

                // Stats row: Check-in time + Presence score
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = spacing.lg),
                    horizontalArrangement = Arrangement.spacedBy(spacing.md)
                ) {
                    // Check-in time card
                    if (attendance.checkInTime != null) {
                        IAMSCard(modifier = Modifier.weight(1f)) {
                            Column(
                                horizontalAlignment = Alignment.CenterHorizontally,
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Icon(
                                    Icons.Outlined.AccessTime,
                                    contentDescription = null,
                                    modifier = Modifier.size(20.dp),
                                    tint = TextTertiary
                                )

                                Spacer(modifier = Modifier.height(spacing.sm))

                                Text(
                                    text = "Check-in Time",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextTertiary
                                )

                                Spacer(modifier = Modifier.height(spacing.xs))

                                Text(
                                    text = formatDisplayTime(attendance.checkInTime),
                                    style = MaterialTheme.typography.bodyLarge,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                        }
                    }

                    // Presence score card
                    if (attendance.presenceScore != null) {
                        IAMSCard(modifier = Modifier.weight(1f)) {
                            Column(
                                horizontalAlignment = Alignment.CenterHorizontally,
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Icon(
                                    Icons.Outlined.TrendingUp,
                                    contentDescription = null,
                                    modifier = Modifier.size(20.dp),
                                    tint = TextTertiary
                                )

                                Spacer(modifier = Modifier.height(spacing.sm))

                                Text(
                                    text = "Presence Score",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextTertiary
                                )

                                Spacer(modifier = Modifier.height(spacing.xs))

                                Text(
                                    text = "${attendance.presenceScore.toInt()}%",
                                    style = MaterialTheme.typography.bodyLarge,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                        }
                    }
                }

                // Scan counts card
                if (attendance.totalScans != null) {
                    IAMSCard(
                        modifier = Modifier.padding(bottom = spacing.lg)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            // Total scans
                            Column(
                                modifier = Modifier.weight(1f),
                                horizontalAlignment = Alignment.CenterHorizontally
                            ) {
                                Text(
                                    text = "Total Scans",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextTertiary
                                )

                                Spacer(modifier = Modifier.height(spacing.xs))

                                Text(
                                    text = "${attendance.totalScans}",
                                    style = MaterialTheme.typography.headlineMedium,
                                    fontWeight = FontWeight.Bold
                                )
                            }

                            // Divider
                            Box(
                                modifier = Modifier
                                    .width(1.dp)
                                    .height(40.dp)
                                    .background(Border)
                            )

                            // Scans present
                            Column(
                                modifier = Modifier.weight(1f),
                                horizontalAlignment = Alignment.CenterHorizontally
                            ) {
                                Text(
                                    text = "Scans Present",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextTertiary
                                )

                                Spacer(modifier = Modifier.height(spacing.xs))

                                Text(
                                    text = "${attendance.scansPresent ?: 0}",
                                    style = MaterialTheme.typography.headlineMedium,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }
                    }
                }

                // Remarks card
                if (attendance.remarks != null) {
                    IAMSCard(
                        modifier = Modifier.padding(bottom = spacing.lg)
                    ) {
                        Text(
                            text = "Remarks",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextTertiary
                        )

                        Spacer(modifier = Modifier.height(spacing.xs))

                        Text(
                            text = attendance.remarks,
                            style = MaterialTheme.typography.bodyMedium,
                            color = TextSecondary
                        )
                    }
                }

                // Divider
                HorizontalDivider(
                    modifier = Modifier.padding(vertical = spacing.xxl),
                    thickness = 1.dp,
                    color = Border
                )

                // Presence Timeline section title
                Text(
                    text = "Presence Timeline",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(bottom = spacing.lg)
                )

                // Presence timeline
                if (uiState.logs.isNotEmpty()) {
                    IAMSCard {
                        uiState.logs.forEachIndexed { index, log ->
                            PresenceLogItem(
                                log = log,
                                isLast = index == uiState.logs.size - 1
                            )
                        }
                    }
                } else {
                    IAMSCard {
                        Text(
                            text = "No presence logs available",
                            style = MaterialTheme.typography.bodyMedium,
                            color = TextSecondary,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }

                Spacer(modifier = Modifier.height(spacing.lg))
            }

        }
    }
}

@Composable
private fun PresenceLogItem(
    log: PresenceLogResponse,
    isLast: Boolean
) {
    val spacing = IAMSThemeTokens.spacing
    val dotColor = if (log.detected) PresentFg else AbsentFg

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = spacing.md)
    ) {
        // Indicator column: dot + connecting line
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(end = spacing.lg)
        ) {
            Box(
                modifier = Modifier
                    .size(12.dp)
                    .clip(CircleShape)
                    .background(dotColor)
            )

            if (!isLast) {
                Box(
                    modifier = Modifier
                        .width(2.dp)
                        .weight(1f)
                        .padding(top = spacing.sm)
                        .background(Border)
                )
            }
        }

        // Content column
        Column(modifier = Modifier.weight(1f)) {
            // Header row: Scan # + time
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = spacing.xs),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Scan #${log.scanNumber}",
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Medium
                )

                Text(
                    text = formatDisplayTime(log.scanTime),
                    style = MaterialTheme.typography.bodySmall,
                    color = TextTertiary
                )
            }

            // Detection status
            Text(
                text = if (log.detected) "Detected" else "Not Detected",
                style = MaterialTheme.typography.bodyMedium,
                color = if (log.detected) PresentFg else AbsentFg
            )

            // Confidence
            if (log.confidence != null) {
                Text(
                    text = "Confidence: ${(log.confidence * 100).toInt()}%",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextTertiary
                )
            }
        }
    }
}

// --- Date/Time formatting helpers ---

private fun formatDisplayDate(dateStr: String): String {
    return try {
        val date = LocalDate.parse(dateStr)
        date.format(DateTimeFormatter.ofPattern("MMM d, yyyy"))
    } catch (e: Exception) {
        dateStr
    }
}

private fun formatDisplayTime(timeStr: String): String {
    return try {
        // Try parsing as full ISO datetime first
        if (timeStr.contains("T")) {
            val dateTime = java.time.LocalDateTime.parse(
                timeStr.substringBefore("Z").substringBefore("+")
            )
            dateTime.format(DateTimeFormatter.ofPattern("h:mm a"))
        } else {
            val time = LocalTime.parse(timeStr)
            time.format(DateTimeFormatter.ofPattern("h:mm a"))
        }
    } catch (e: Exception) {
        timeStr
    }
}

private fun parseStatus(status: String): AttendanceStatus {
    return when (status.lowercase()) {
        "present" -> AttendanceStatus.PRESENT
        "late" -> AttendanceStatus.LATE
        "absent" -> AttendanceStatus.ABSENT
        "early_leave" -> AttendanceStatus.EARLY_LEAVE
        else -> AttendanceStatus.ABSENT
    }
}
