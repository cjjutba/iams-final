package com.iams.app.ui.student

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.EmojiEvents
import androidx.compose.material.icons.outlined.LocalFireDepartment
import androidx.compose.material.icons.outlined.Remove
import androidx.compose.material.icons.outlined.TrendingDown
import androidx.compose.material.icons.outlined.TrendingUp
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.SubjectBreakdown
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.components.SkeletonBox
import com.iams.app.ui.theme.AbsentBg
import com.iams.app.ui.theme.AbsentBorder
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.EarlyLeaveFg
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.LateBg
import com.iams.app.ui.theme.LateBorder
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.PresentBg
import com.iams.app.ui.theme.PresentBorder
import com.iams.app.ui.theme.PresentFg
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import kotlin.math.min
import kotlin.math.roundToInt

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudentAnalyticsScreen(
    navController: NavController,
    viewModel: StudentAnalyticsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        IAMSHeader(
            title = "My Analytics",
            onBack = { navController.popBackStack() },
        )

        // Loading skeleton
        if (uiState.isLoading && !uiState.isRefreshing) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(spacing.screenPadding)
                    .padding(bottom = spacing.xxxl)
            ) {
                // Hero card skeleton
                IAMSCard(modifier = Modifier.padding(bottom = spacing.lg)) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = spacing.xxl)
                    ) {
                        SkeletonBox(width = 140.dp, height = 12.dp)
                        Spacer(modifier = Modifier.height(spacing.md))
                        SkeletonBox(width = 100.dp, height = 56.dp, cornerRadius = 8.dp)
                        Spacer(modifier = Modifier.height(spacing.lg))
                        SkeletonBox(height = 10.dp, cornerRadius = 9999.dp)
                        Spacer(modifier = Modifier.height(spacing.md))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            SkeletonBox(width = 120.dp, height = 12.dp)
                            SkeletonBox(width = 80.dp, height = 12.dp)
                        }
                    }
                }

                // Metrics row skeleton (3 cards)
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = spacing.xxl),
                    horizontalArrangement = Arrangement.spacedBy(spacing.md)
                ) {
                    repeat(3) {
                        IAMSCard(modifier = Modifier.weight(1f)) {
                            Column(
                                horizontalAlignment = Alignment.CenterHorizontally,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = spacing.lg)
                            ) {
                                SkeletonBox(width = 20.dp, height = 20.dp, cornerRadius = 10.dp)
                                Spacer(modifier = Modifier.height(spacing.sm))
                                SkeletonBox(width = 40.dp, height = 28.dp, cornerRadius = 4.dp)
                                Spacer(modifier = Modifier.height(spacing.xs))
                                SkeletonBox(width = 56.dp, height = 12.dp)
                            }
                        }
                    }
                }

                // Subjects section title skeleton
                SkeletonBox(
                    width = 80.dp,
                    height = 22.dp,
                    modifier = Modifier.padding(bottom = spacing.md)
                )

                // Subject card skeletons
                repeat(2) {
                    IAMSCard(modifier = Modifier.padding(bottom = spacing.md)) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(bottom = spacing.md),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Column {
                                SkeletonBox(width = 140.dp, height = 14.dp)
                                Spacer(modifier = Modifier.height(4.dp))
                                SkeletonBox(width = 80.dp, height = 12.dp)
                            }
                            SkeletonBox(width = 44.dp, height = 24.dp, cornerRadius = 4.dp)
                        }
                        SkeletonBox(
                            height = 8.dp,
                            cornerRadius = 9999.dp,
                            modifier = Modifier.padding(bottom = spacing.sm)
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            SkeletonBox(width = 120.dp, height = 12.dp)
                            SkeletonBox(width = 100.dp, height = 12.dp)
                        }
                    }
                }
            }
            return@Column
        }

        // Error state (no dashboard data)
        if (uiState.error != null && uiState.dashboard == null) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.padding(horizontal = spacing.xxl)
                ) {
                    Icon(
                        Icons.Outlined.EmojiEvents,
                        contentDescription = null,
                        modifier = Modifier.size(40.dp),
                        tint = TextTertiary
                    )

                    Spacer(modifier = Modifier.height(spacing.lg))

                    Text(
                        text = uiState.error ?: "",
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextSecondary,
                        textAlign = TextAlign.Center
                    )

                    Spacer(modifier = Modifier.height(spacing.lg))

                    IAMSButton(
                        text = "Tap to Retry",
                        onClick = { viewModel.refresh() },
                        variant = IAMSButtonVariant.GHOST,
                        fullWidth = false
                    )
                }
            }
            return@Column
        }

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
                    .padding(bottom = spacing.xxxl)
            ) {
                val dashboard = uiState.dashboard
                val overallRate = dashboard?.let {
                    it.overallAttendanceRate.roundToInt()
                } ?: 0

                // Hero Card - Overall Attendance
                IAMSCard(
                    modifier = Modifier.padding(bottom = spacing.lg)
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = spacing.xxl)
                    ) {
                        // OVERALL ATTENDANCE label
                        Text(
                            text = "OVERALL ATTENDANCE",
                            style = MaterialTheme.typography.bodySmall.copy(
                                fontWeight = FontWeight.SemiBold,
                                letterSpacing = 1.sp
                            ),
                            color = TextSecondary,
                            modifier = Modifier.padding(bottom = spacing.sm)
                        )

                        // Large percentage display
                        Row(
                            verticalAlignment = Alignment.Bottom,
                            modifier = Modifier.padding(bottom = spacing.lg)
                        ) {
                            Text(
                                text = "$overallRate",
                                style = TextStyle(
                                    fontSize = 64.sp,
                                    fontWeight = FontWeight.Bold,
                                    lineHeight = 72.sp
                                ),
                                color = getAttendanceColor(overallRate)
                            )
                            Text(
                                text = "%",
                                style = TextStyle(
                                    fontSize = 28.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    lineHeight = 40.sp
                                ),
                                color = getAttendanceColor(overallRate),
                                modifier = Modifier.padding(bottom = 8.dp, start = 2.dp)
                            )
                        }

                        // Progress bar
                        AttendanceProgressBar(
                            rate = overallRate,
                            height = 10.dp,
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(bottom = spacing.md)
                        )

                        // Stats row under bar
                        if (dashboard != null) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "${dashboard.totalClassesAttended} of ${dashboard.totalClasses} classes",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextSecondary
                                )

                                // Trend indicator
                                val trendInfo = getTrendInfo(dashboard.trend)
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        trendInfo.icon,
                                        contentDescription = null,
                                        modifier = Modifier.size(14.dp),
                                        tint = trendInfo.color
                                    )
                                    Spacer(modifier = Modifier.width(spacing.xs))
                                    Text(
                                        text = trendInfo.label,
                                        style = MaterialTheme.typography.bodySmall.copy(
                                            fontWeight = FontWeight.SemiBold
                                        ),
                                        color = trendInfo.color
                                    )
                                }
                            }
                        }
                    }
                }

                // Metrics Row: Streak, Rank, Early Leaves
                if (dashboard != null) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = spacing.xxl),
                        horizontalArrangement = Arrangement.spacedBy(spacing.md)
                    ) {
                        // Current Streak
                        IAMSCard(modifier = Modifier.weight(1f)) {
                            Column(
                                horizontalAlignment = Alignment.CenterHorizontally,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = spacing.lg, horizontal = spacing.sm)
                            ) {
                                Icon(
                                    Icons.Outlined.LocalFireDepartment,
                                    contentDescription = null,
                                    modifier = Modifier.size(20.dp),
                                    tint = if (dashboard.currentStreak > 0) EarlyLeaveFg else TextTertiary
                                )

                                Spacer(modifier = Modifier.height(spacing.sm))

                                Text(
                                    text = "${dashboard.currentStreak}",
                                    style = MaterialTheme.typography.headlineLarge,
                                    fontWeight = FontWeight.Bold
                                )

                                Spacer(modifier = Modifier.height(spacing.xs))

                                Text(
                                    text = "Day Streak",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextSecondary,
                                    textAlign = TextAlign.Center
                                )

                                if (dashboard.longestStreak > 0) {
                                    Spacer(modifier = Modifier.height(spacing.xs))
                                    Text(
                                        text = "Best: ${dashboard.longestStreak}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = TextTertiary
                                    )
                                }
                            }
                        }

                        // Class Rank
                        IAMSCard(modifier = Modifier.weight(1f)) {
                            Column(
                                horizontalAlignment = Alignment.CenterHorizontally,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = spacing.lg, horizontal = spacing.sm)
                            ) {
                                Icon(
                                    Icons.Outlined.EmojiEvents,
                                    contentDescription = null,
                                    modifier = Modifier.size(20.dp),
                                    tint = TextSecondary
                                )

                                Spacer(modifier = Modifier.height(spacing.sm))

                                Text(
                                    text = if (dashboard.rankInClass != null) "#${dashboard.rankInClass}" else "--",
                                    style = MaterialTheme.typography.headlineLarge,
                                    fontWeight = FontWeight.Bold
                                )

                                Spacer(modifier = Modifier.height(spacing.xs))

                                Text(
                                    text = "Class Rank",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextSecondary,
                                    textAlign = TextAlign.Center
                                )

                                if (dashboard.totalStudents != null) {
                                    Spacer(modifier = Modifier.height(spacing.xs))
                                    Text(
                                        text = "of ${dashboard.totalStudents}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = TextTertiary
                                    )
                                }
                            }
                        }

                        // Early Leaves
                        IAMSCard(modifier = Modifier.weight(1f)) {
                            Column(
                                horizontalAlignment = Alignment.CenterHorizontally,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = spacing.lg, horizontal = spacing.sm)
                            ) {
                                Icon(
                                    Icons.Outlined.TrendingDown,
                                    contentDescription = null,
                                    modifier = Modifier.size(20.dp),
                                    tint = if (dashboard.earlyLeaveCount > 0) EarlyLeaveFg else TextTertiary
                                )

                                Spacer(modifier = Modifier.height(spacing.sm))

                                Text(
                                    text = "${dashboard.earlyLeaveCount}",
                                    style = MaterialTheme.typography.headlineLarge,
                                    fontWeight = FontWeight.Bold
                                )

                                Spacer(modifier = Modifier.height(spacing.xs))

                                Text(
                                    text = "Early Leaves",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextSecondary,
                                    textAlign = TextAlign.Center,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis
                                )
                            }
                        }
                    }
                }

                // Subjects Section
                Text(
                    text = "Subjects",
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(bottom = spacing.md)
                )

                if (uiState.subjects.isEmpty()) {
                    // Empty state card
                    IAMSCard(
                        modifier = Modifier.padding(bottom = spacing.md)
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = spacing.xxxl)
                        ) {
                            Text(
                                text = "No subject data available.",
                                style = MaterialTheme.typography.bodyLarge,
                                color = TextSecondary,
                                textAlign = TextAlign.Center
                            )

                            Spacer(modifier = Modifier.height(spacing.sm))

                            Text(
                                text = "Subject breakdowns will appear after your attendance is recorded.",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextTertiary,
                                textAlign = TextAlign.Center
                            )
                        }
                    }
                } else {
                    uiState.subjects.forEach { subject ->
                        SubjectCard(
                            subject = subject,
                            modifier = Modifier.padding(bottom = spacing.md)
                        )
                    }
                }
            }

        }
    }
}

// --- Subject Card ---

@Composable
private fun SubjectCard(
    subject: SubjectBreakdown,
    modifier: Modifier = Modifier
) {
    val spacing = IAMSThemeTokens.spacing
    val rate = subject.attendanceRate.roundToInt()

    IAMSCard(modifier = modifier) {
        // Header: subject name + rate
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = spacing.md),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top
        ) {
            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(end = spacing.md)
            ) {
                Text(
                    text = subject.subjectName,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )

                if (subject.subjectCode != null) {
                    Text(
                        text = subject.subjectCode,
                        style = MaterialTheme.typography.bodySmall,
                        color = TextTertiary
                    )
                }
            }

            Text(
                text = "$rate%",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = getAttendanceColor(rate)
            )
        }

        // Progress bar
        AttendanceProgressBar(
            rate = rate,
            height = 8.dp,
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = spacing.sm)
        )

        // Footer: sessions + last attended
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "${subject.sessionsAttended} of ${subject.sessionsTotal} sessions",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )

            if (subject.lastAttended != null) {
                Text(
                    text = "Last: ${formatSubjectDate(subject.lastAttended)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextTertiary
                )
            }
        }
    }
}

// --- Progress Bar ---

@Composable
private fun AttendanceProgressBar(
    rate: Int,
    height: androidx.compose.ui.unit.Dp,
    modifier: Modifier = Modifier
) {
    val fillFraction = min(rate, 100) / 100f
    val barBg = getAttendanceBarBg(rate)
    val barBorder = getAttendanceBarBorder(rate)
    val pillShape = RoundedCornerShape(9999.dp)

    Box(
        modifier = modifier
            .height(height)
            .clip(pillShape)
            .background(Secondary)
    ) {
        if (fillFraction > 0f) {
            Box(
                modifier = Modifier
                    .fillMaxWidth(fillFraction)
                    .height(height)
                    .clip(pillShape)
                    .background(barBg)
                    .border(1.dp, barBorder, pillShape)
            )
        }
    }
}

// --- Helper functions ---

private fun getAttendanceColor(rate: Int): Color {
    return when {
        rate >= 80 -> PresentFg
        rate >= 60 -> LateFg
        else -> AbsentFg
    }
}

private fun getAttendanceBarBg(rate: Int): Color {
    return when {
        rate >= 80 -> PresentBg
        rate >= 60 -> LateBg
        else -> AbsentBg
    }
}

private fun getAttendanceBarBorder(rate: Int): Color {
    return when {
        rate >= 80 -> PresentBorder
        rate >= 60 -> LateBorder
        else -> AbsentBorder
    }
}

private data class TrendInfo(
    val icon: ImageVector,
    val label: String,
    val color: Color
)

private fun getTrendInfo(trend: String): TrendInfo {
    return when (trend) {
        "improving" -> TrendInfo(
            icon = Icons.Outlined.TrendingUp,
            label = "Improving",
            color = PresentFg
        )
        "declining" -> TrendInfo(
            icon = Icons.Outlined.TrendingDown,
            label = "Declining",
            color = AbsentFg
        )
        else -> TrendInfo(
            icon = Icons.Outlined.Remove,
            label = "Stable",
            color = TextSecondary
        )
    }
}

private fun formatSubjectDate(dateStr: String): String {
    return try {
        val date = LocalDate.parse(dateStr.substringBefore("T"))
        date.format(DateTimeFormatter.ofPattern("M/d/yyyy"))
    } catch (e: Exception) {
        dateStr
    }
}
