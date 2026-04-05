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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material3.CircularProgressIndicator
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
import com.iams.app.data.model.AlertResponse
import com.iams.app.ui.components.CardSkeleton
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.components.NotificationBellButton
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.AbsentBg
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.EarlyLeaveBg
import com.iams.app.ui.theme.EarlyLeaveFg
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.PresentBg
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.PrimaryForeground
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import java.time.Duration
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultyAlertsScreen(
    navController: NavController,
    viewModel: FacultyAlertsViewModel = hiltViewModel()
) {
    Column(modifier = Modifier.fillMaxSize()) {
        IAMSHeader(
            title = "Alerts",
            trailing = {
                NotificationBellButton(
                    notificationService = viewModel.notificationService,
                    onClick = { navController.navigate(Routes.FACULTY_NOTIFICATIONS) },
                )
            },
        )

        FacultyAlertsContent(navController = navController, viewModel = viewModel)
    }
}

/**
 * Alerts content body (filter bar + list) without the IAMSHeader/Scaffold wrapper.
 * Reused inside FacultyHistoryScreen's "Alerts" tab.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultyAlertsContent(
    navController: NavController,
    viewModel: FacultyAlertsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing

    Column(modifier = Modifier.fillMaxSize()) {
        // Error state (no data)
        if (uiState.error != null && !uiState.isRefreshing && uiState.alerts.isEmpty()) {
            FilterBar(
                selectedFilter = uiState.selectedFilter,
                onFilterSelected = { viewModel.selectFilter(it) },
            )

            ErrorState(onRetry = { viewModel.loadAlerts() })
            return
        }

        // Filter buttons
        FilterBar(
            selectedFilter = uiState.selectedFilter,
            onFilterSelected = { viewModel.selectFilter(it) },
        )

        // Loading state (skeleton cards)
        if (uiState.isLoading && uiState.alerts.isEmpty()) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(spacing.lg),
                verticalArrangement = Arrangement.spacedBy(spacing.sm),
            ) {
                repeat(4) {
                    CardSkeleton()
                }
            }
            return
        }

        // Alerts list
        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize(),
        ) {
            LazyColumn(
                contentPadding = PaddingValues(spacing.lg),
                modifier = Modifier.fillMaxSize(),
            ) {
                if (uiState.alerts.isEmpty()) {
                    item {
                        AlertsEmptyState()
                    }
                } else {
                    items(uiState.alerts, key = { it.id }) { alert ->
                        AlertCard(
                            alert = alert,
                            onClick = {
                                val studentId = alert.studentId
                                val scheduleId = alert.scheduleId
                                if (studentId != null && scheduleId != null) {
                                    navController.navigate("studentDetail/$studentId/$scheduleId")
                                }
                            }
                        )
                        Spacer(modifier = Modifier.height(spacing.sm))
                    }
                }
            }
        }
    }
}

@Composable
private fun FilterBar(
    selectedFilter: AlertFilter,
    onFilterSelected: (AlertFilter) -> Unit,
) {
    val spacing = IAMSThemeTokens.spacing

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = spacing.lg, vertical = spacing.lg),
        horizontalArrangement = Arrangement.spacedBy(spacing.sm),
    ) {
        AlertFilter.entries.forEach { filter ->
            val isSelected = filter == selectedFilter
            Box(
                contentAlignment = Alignment.Center,
                modifier = Modifier
                    .height(40.dp)
                    .clip(RoundedCornerShape(9999.dp))
                    .background(if (isSelected) Primary else Secondary)
                    .clickable { onFilterSelected(filter) }
                    .padding(horizontal = 16.dp),
            ) {
                Text(
                    text = filter.label,
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
                    color = if (isSelected) PrimaryForeground else TextSecondary,
                )
            }
        }
    }

    HorizontalDivider(thickness = 1.dp, color = Border)
}

@Composable
private fun AlertCard(
    alert: AlertResponse,
    onClick: () -> Unit,
) {
    val spacing = IAMSThemeTokens.spacing

    IAMSCard(onClick = onClick) {
        Row(
            verticalAlignment = Alignment.Top,
            modifier = Modifier.fillMaxWidth(),
        ) {
            // Warning icon
            Icon(
                Icons.Default.Warning,
                contentDescription = null,
                modifier = Modifier.size(24.dp),
                tint = EarlyLeaveFg,
            )

            Spacer(modifier = Modifier.width(spacing.md))

            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = alert.studentName ?: "Unknown Student",
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.weight(1f),
                    )
                    if (alert.returned) {
                        Text(
                            text = "✓ Returned",
                            style = MaterialTheme.typography.labelSmall,
                            color = PresentFg,
                            fontWeight = FontWeight.SemiBold,
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(PresentBg)
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    } else {
                        Text(
                            text = "Still Absent",
                            style = MaterialTheme.typography.labelSmall,
                            color = AbsentFg,
                            fontWeight = FontWeight.SemiBold,
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(AbsentBg)
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                }
                Spacer(modifier = Modifier.height(spacing.xs))
                val displayMessage = if (alert.returned && alert.returnedAt != null) {
                    "Left early · Returned at ${formatAlertTime(alert.returnedAt)}"
                } else {
                    alert.message ?: "Early leave detected"
                }
                Text(
                    text = displayMessage,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary,
                )
                Spacer(modifier = Modifier.height(spacing.sm))
                Text(
                    text = formatTimeAgo(alert.createdAt ?: alert.detectedAt ?: ""),
                    style = MaterialTheme.typography.bodySmall,
                    color = TextTertiary,
                )
            }
        }
    }
}

@Composable
private fun AlertsEmptyState() {
    val spacing = IAMSThemeTokens.spacing

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            Icons.Default.Warning,
            contentDescription = null,
            modifier = Modifier.size(48.dp),
            tint = TextTertiary,
        )
        Spacer(modifier = Modifier.height(spacing.lg))
        Text(
            text = "No alerts today",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = TextAlign.Center,
        )
        Spacer(modifier = Modifier.height(spacing.sm))
        Text(
            text = "No early leave alerts for the selected period",
            style = MaterialTheme.typography.bodySmall,
            color = TextTertiary,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun ErrorState(onRetry: () -> Unit) {
    val spacing = IAMSThemeTokens.spacing

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = spacing.xxl),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            Icons.Default.Refresh,
            contentDescription = null,
            modifier = Modifier.size(40.dp),
            tint = TextTertiary,
        )
        Spacer(modifier = Modifier.height(spacing.lg))
        Text(
            text = "Unable to load alerts. Please try again.",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = TextAlign.Center,
        )
        Spacer(modifier = Modifier.height(spacing.lg))
        IAMSButton(
            text = "Retry",
            onClick = onRetry,
            variant = IAMSButtonVariant.SECONDARY,
            fullWidth = false,
        )
    }
}

/** Format a timestamp string into a relative "time ago" string. */
private fun formatTimeAgo(timestamp: String): String {
    if (timestamp.isBlank()) return ""
    return try {
        val parsed = ZonedDateTime.parse(timestamp)
        val now = ZonedDateTime.now()
        val duration = Duration.between(parsed, now)

        when {
            duration.toMinutes() < 1 -> "Just now"
            duration.toMinutes() < 60 -> "${duration.toMinutes()}m ago"
            duration.toHours() < 24 -> "${duration.toHours()}h ago"
            duration.toDays() < 7 -> "${duration.toDays()}d ago"
            else -> parsed.format(DateTimeFormatter.ofPattern("MMM d, yyyy"))
        }
    } catch (_: Exception) {
        try {
            // Try parsing as LocalDateTime without timezone
            val parsed = java.time.LocalDateTime.parse(timestamp.replace(" ", "T"))
            val now = java.time.LocalDateTime.now()
            val duration = Duration.between(parsed, now)

            when {
                duration.toMinutes() < 1 -> "Just now"
                duration.toMinutes() < 60 -> "${duration.toMinutes()}m ago"
                duration.toHours() < 24 -> "${duration.toHours()}h ago"
                duration.toDays() < 7 -> "${duration.toDays()}d ago"
                else -> parsed.format(DateTimeFormatter.ofPattern("MMM d, yyyy"))
            }
        } catch (_: Exception) {
            timestamp
        }
    }
}

/** Format an ISO timestamp to display time only (e.g., "3:15 PM"). */
private fun formatAlertTime(timestamp: String): String {
    if (timestamp.isBlank()) return ""
    return try {
        val parsed = ZonedDateTime.parse(timestamp)
        parsed.format(DateTimeFormatter.ofPattern("h:mm a"))
    } catch (_: Exception) {
        try {
            val parsed = java.time.LocalDateTime.parse(timestamp.replace(" ", "T"))
            parsed.format(DateTimeFormatter.ofPattern("h:mm a"))
        } catch (_: Exception) {
            timestamp
        }
    }
}
