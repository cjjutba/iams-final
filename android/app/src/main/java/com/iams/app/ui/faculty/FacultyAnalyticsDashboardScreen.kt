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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material.icons.filled.TrendingDown
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.AnomalyItem
import com.iams.app.data.model.AtRiskStudent
import com.iams.app.data.model.ClassOverview
import com.iams.app.ui.components.CardSkeleton
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.components.NotificationBellButton
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.components.SkeletonBox
import com.iams.app.ui.theme.AbsentBg
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.EarlyLeaveFg
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.LateBg
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.PresentBg
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import kotlin.math.roundToInt

// Helper functions
private fun getAttendanceColor(rate: Float): Color = when {
    rate >= 80f -> PresentFg
    rate >= 60f -> LateFg
    else -> AbsentFg
}

private fun getAttendanceBarBg(rate: Float): Color = when {
    rate >= 80f -> PresentBg
    rate >= 60f -> LateBg
    else -> AbsentBg
}

private fun getRiskColor(level: String): Color = when (level) {
    "critical" -> AbsentFg
    "high" -> EarlyLeaveFg
    "medium" -> LateFg
    else -> TextSecondary
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultyAnalyticsDashboardScreen(
    navController: NavController,
    viewModel: FacultyAnalyticsDashboardViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        IAMSHeader(
            title = "Analytics",
            trailing = {
                NotificationBellButton(
                    notificationService = viewModel.notificationService,
                    onClick = { navController.navigate(Routes.FACULTY_NOTIFICATIONS) },
                )
            },
        )

        when {
            // Loading — skeleton placeholders
            uiState.isLoading && !uiState.isRefreshing -> {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(spacing.screenPadding)
                ) {
                    // Summary cards skeleton
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(spacing.md)
                    ) {
                        IAMSCard(modifier = Modifier.weight(1f)) {
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = spacing.lg),
                                horizontalAlignment = Alignment.CenterHorizontally
                            ) {
                                SkeletonBox(width = 20.dp, height = 20.dp, cornerRadius = 4.dp)
                                Spacer(modifier = Modifier.height(spacing.sm))
                                SkeletonBox(width = 40.dp, height = 28.dp)
                                Spacer(modifier = Modifier.height(spacing.xs))
                                SkeletonBox(width = 80.dp, height = 12.dp)
                            }
                        }
                        IAMSCard(modifier = Modifier.weight(1f)) {
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = spacing.lg),
                                horizontalAlignment = Alignment.CenterHorizontally
                            ) {
                                SkeletonBox(width = 20.dp, height = 20.dp, cornerRadius = 4.dp)
                                Spacer(modifier = Modifier.height(spacing.sm))
                                SkeletonBox(width = 40.dp, height = 28.dp)
                                Spacer(modifier = Modifier.height(spacing.xs))
                                SkeletonBox(width = 80.dp, height = 12.dp)
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    SkeletonBox(width = 140.dp, height = 20.dp)
                    Spacer(modifier = Modifier.height(spacing.md))
                    repeat(3) {
                        CardSkeleton()
                        Spacer(modifier = Modifier.height(spacing.md))
                    }
                }
            }

            // Error
            uiState.error != null && uiState.classOverviews.isEmpty() -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        modifier = Modifier.padding(horizontal = spacing.xxl)
                    ) {
                        Icon(
                            Icons.Default.BarChart,
                            contentDescription = "Analytics",
                            modifier = Modifier.size(40.dp),
                            tint = TextTertiary
                        )
                        Spacer(modifier = Modifier.height(spacing.lg))
                        Text(
                            text = uiState.error!!,
                            style = MaterialTheme.typography.bodyLarge,
                            color = TextSecondary,
                            textAlign = TextAlign.Center
                        )
                        Spacer(modifier = Modifier.height(spacing.lg))
                        IAMSButton(
                            text = "Tap to Retry",
                            onClick = { viewModel.loadData() },
                            variant = IAMSButtonVariant.GHOST,
                            fullWidth = false
                        )
                    }
                }
            }

            // Content
            else -> {
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
                        // Summary cards row
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(spacing.md)
                        ) {
                            // At-Risk Students Card
                            IAMSCard(modifier = Modifier.weight(1f)) {
                                Column(
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = spacing.lg)
                                ) {
                                    Icon(
                                        Icons.Default.TrendingDown,
                                        contentDescription = "At-Risk",
                                        modifier = Modifier.size(20.dp),
                                        tint = if (uiState.atRiskCount > 0) AbsentFg else TextTertiary
                                    )
                                    Spacer(modifier = Modifier.height(spacing.sm))
                                    Text(
                                        text = "${uiState.atRiskCount}",
                                        style = MaterialTheme.typography.headlineLarge,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Spacer(modifier = Modifier.height(spacing.xs))
                                    Text(
                                        text = "At-Risk Students",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextSecondary,
                                        maxLines = 1
                                    )
                                    if (uiState.highRiskCount > 0) {
                                        Spacer(modifier = Modifier.height(spacing.xs))
                                        Text(
                                            text = "${uiState.highRiskCount} high/critical",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = AbsentFg
                                        )
                                    }
                                }
                            }

                            // Anomaly Alerts Card
                            IAMSCard(modifier = Modifier.weight(1f)) {
                                Column(
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = spacing.lg)
                                ) {
                                    Icon(
                                        Icons.Default.Warning,
                                        contentDescription = "Anomalies",
                                        modifier = Modifier.size(20.dp),
                                        tint = if (uiState.unresolvedAnomalyCount > 0) LateFg else TextTertiary
                                    )
                                    Spacer(modifier = Modifier.height(spacing.sm))
                                    Text(
                                        text = "${uiState.unresolvedAnomalyCount}",
                                        style = MaterialTheme.typography.headlineLarge,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Spacer(modifier = Modifier.height(spacing.xs))
                                    Text(
                                        text = "Anomaly Alerts",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextSecondary,
                                        maxLines = 1
                                    )
                                    if (uiState.unresolvedAnomalyCount > 0) {
                                        Spacer(modifier = Modifier.height(spacing.xs))
                                        Text(
                                            text = "Unresolved",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = LateFg
                                        )
                                    }
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(spacing.xxl))

                        // Class Attendance Section
                        Text(
                            text = "Class Attendance",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.SemiBold
                        )
                        Spacer(modifier = Modifier.height(spacing.md))

                        if (uiState.classOverviews.isEmpty()) {
                            IAMSCard {
                                Column(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = spacing.xxxl),
                                    horizontalAlignment = Alignment.CenterHorizontally
                                ) {
                                    Text(
                                        text = "No class data available yet.",
                                        style = MaterialTheme.typography.bodyLarge,
                                        color = TextSecondary,
                                        textAlign = TextAlign.Center
                                    )
                                    Spacer(modifier = Modifier.height(spacing.sm))
                                    Text(
                                        text = "Analytics will appear after classes have sessions recorded.",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextTertiary,
                                        textAlign = TextAlign.Center
                                    )
                                }
                            }
                        } else {
                            uiState.classOverviews.forEach { overview ->
                                ClassOverviewCard(overview = overview)
                                Spacer(modifier = Modifier.height(spacing.md))
                            }
                        }

                        // At-Risk Students List
                        if (uiState.atRiskStudents.isNotEmpty()) {
                            Spacer(modifier = Modifier.height(spacing.sm))
                            Text(
                                text = "At-Risk Students",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.SemiBold
                            )
                            Spacer(modifier = Modifier.height(spacing.md))

                            uiState.atRiskStudents.take(5).forEach { student ->
                                AtRiskStudentCard(student = student)
                                Spacer(modifier = Modifier.height(spacing.md))
                            }

                            if (uiState.atRiskStudents.size > 5) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = spacing.md),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = "View All ${uiState.atRiskStudents.size} At-Risk Students",
                                        style = MaterialTheme.typography.bodySmall,
                                        fontWeight = FontWeight.SemiBold,
                                        color = Primary
                                    )
                                }
                            }
                        }

                        // Anomaly Alerts List
                        if (uiState.anomalies.isNotEmpty()) {
                            Spacer(modifier = Modifier.height(spacing.sm))
                            Text(
                                text = "Recent Anomalies",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.SemiBold
                            )
                            Spacer(modifier = Modifier.height(spacing.md))

                            uiState.anomalies.take(3).forEach { anomaly ->
                                AnomalyCard(anomaly = anomaly)
                                Spacer(modifier = Modifier.height(spacing.md))
                            }

                            if (uiState.anomalies.size > 3) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = spacing.md),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = "View All ${uiState.anomalies.size} Anomalies",
                                        style = MaterialTheme.typography.bodySmall,
                                        fontWeight = FontWeight.SemiBold,
                                        color = Primary
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ClassOverviewCard(overview: ClassOverview) {
    val spacing = IAMSThemeTokens.spacing
    val rate = overview.averageAttendanceRate.roundToInt()
    val textColor = getAttendanceColor(rate.toFloat())
    val barBg = getAttendanceBarBg(rate.toFloat())

    IAMSCard {
        // Header: subject name + rate
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = overview.subjectName,
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                val subtitle = buildString {
                    overview.subjectCode?.let { append(it) }
                    if (overview.dayName.isNotEmpty()) {
                        if (isNotEmpty()) append(" \u00B7 ")
                        append(overview.dayName)
                    }
                    if (overview.startTime != null && overview.endTime != null) {
                        if (isNotEmpty()) append(" \u00B7 ")
                        append("${overview.startTime} - ${overview.endTime}")
                    }
                }
                if (subtitle.isNotEmpty()) {
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.labelSmall,
                        color = TextTertiary,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
            Spacer(modifier = Modifier.width(spacing.md))
            Text(
                text = "$rate%",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = textColor
            )
        }

        Spacer(modifier = Modifier.height(spacing.md))

        // Attendance rate bar
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(8.dp)
                .clip(RoundedCornerShape(50))
                .background(Secondary)
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth(fraction = (rate.coerceIn(0, 100) / 100f))
                    .height(8.dp)
                    .clip(RoundedCornerShape(50))
                    .background(barBg)
            )
        }

        Spacer(modifier = Modifier.height(spacing.md))

        // Stats row
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            AnalyticsStatItem(label = "Sessions", value = "${overview.totalSessions}")
            AnalyticsStatItem(label = "Enrolled", value = "${overview.totalEnrolled}")
            AnalyticsStatItem(label = "Early Leaves", value = "${overview.earlyLeaveCount}")
            if (overview.anomalyCount > 0) {
                AnalyticsStatItem(
                    label = "Anomalies",
                    value = "${overview.anomalyCount}",
                    highlight = true
                )
            }
        }
    }
}

@Composable
private fun AnalyticsStatItem(
    label: String,
    value: String,
    highlight: Boolean = false
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = value,
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.SemiBold,
            color = if (highlight) LateFg else Primary
        )
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = TextTertiary
        )
    }
}

@Composable
private fun AtRiskStudentCard(student: AtRiskStudent) {
    val spacing = IAMSThemeTokens.spacing
    val riskColor = getRiskColor(student.riskLevel)
    val rate = student.attendanceRate.roundToInt()
    val barBg = getAttendanceBarBg(student.attendanceRate)

    IAMSCard {
        // Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = student.studentName,
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = "${student.subjectName} (${student.subjectCode ?: ""})",
                    style = MaterialTheme.typography.labelSmall,
                    color = TextTertiary
                )
            }
            Spacer(modifier = Modifier.width(spacing.md))
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = "$rate%",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Bold,
                    color = riskColor
                )
                Spacer(modifier = Modifier.height(spacing.xs))
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(4.dp))
                        .background(riskColor.copy(alpha = 0.12f))
                        .padding(horizontal = spacing.sm, vertical = 2.dp)
                ) {
                    Text(
                        text = student.riskLevel.uppercase(),
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = riskColor
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(spacing.md))

        // Attendance bar
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(8.dp)
                .clip(RoundedCornerShape(50))
                .background(Secondary)
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth(fraction = (student.attendanceRate.coerceIn(0f, 100f) / 100f))
                    .height(8.dp)
                    .clip(RoundedCornerShape(50))
                    .background(barBg)
            )
        }

        Spacer(modifier = Modifier.height(spacing.md))

        Text(
            text = "${student.sessionsMissed} of ${student.sessionsTotal} sessions missed",
            style = MaterialTheme.typography.labelSmall,
            color = TextTertiary
        )
    }
}

@Composable
private fun AnomalyCard(anomaly: AnomalyItem) {
    val spacing = IAMSThemeTokens.spacing
    val severityColor = when (anomaly.severity) {
        "high" -> AbsentFg
        "medium" -> LateFg
        else -> TextSecondary
    }

    val formattedDate = try {
        val parsed = ZonedDateTime.parse(anomaly.detectedAt)
        parsed.format(DateTimeFormatter.ofPattern("MM/dd/yyyy hh:mm a"))
    } catch (_: Exception) {
        anomaly.detectedAt
    }

    IAMSCard {
        Row(
            verticalAlignment = Alignment.Top
        ) {
            Icon(
                Icons.Default.Warning,
                contentDescription = "Anomaly",
                modifier = Modifier.size(16.dp),
                tint = severityColor
            )
            Spacer(modifier = Modifier.width(spacing.md))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = anomaly.description,
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = buildString {
                        anomaly.subjectName?.let { append("$it - ") }
                        append(formattedDate)
                    },
                    style = MaterialTheme.typography.labelSmall,
                    color = TextTertiary
                )
            }
            Spacer(modifier = Modifier.width(spacing.sm))
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(4.dp))
                    .background(severityColor.copy(alpha = 0.12f))
                    .padding(horizontal = spacing.sm, vertical = 2.dp)
            ) {
                Text(
                    text = anomaly.severity.uppercase(),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = severityColor
                )
            }
        }
    }
}
