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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
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
import com.iams.app.data.model.NotificationResponse
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.InfoFg
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import java.time.Duration
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultyNotificationsScreen(
    navController: NavController,
    viewModel: FacultyNotificationsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing

    Column(modifier = Modifier.fillMaxSize()) {
        IAMSHeader(
            title = "Notifications",
            onBack = { navController.popBackStack() }
        )

        // Error state (no data)
        if (uiState.error != null && !uiState.isRefreshing && uiState.notifications.isEmpty()) {
            NotificationsErrorState(onRetry = { viewModel.loadNotifications() })
            return
        }

        // Loading state (no data)
        if (uiState.isLoading && uiState.notifications.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center,
            ) {
                CircularProgressIndicator()
            }
            return
        }

        // Notifications list
        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize(),
        ) {
            LazyColumn(
                contentPadding = PaddingValues(spacing.lg),
                modifier = Modifier.fillMaxSize(),
            ) {
                if (uiState.notifications.isEmpty()) {
                    item {
                        NotificationsEmptyState()
                    }
                } else {
                    items(uiState.notifications, key = { it.id }) { notification ->
                        NotificationItem(
                            notification = notification,
                            isMarkingRead = uiState.markingReadIds.contains(notification.id),
                            onMarkAsRead = {
                                if (!notification.read && !uiState.markingReadIds.contains(notification.id)) {
                                    viewModel.markAsRead(notification.id)
                                }
                            }
                        )
                        Spacer(modifier = Modifier.height(spacing.md))
                    }
                }
            }
        }
    }
}

@Composable
private fun NotificationItem(
    notification: NotificationResponse,
    isMarkingRead: Boolean,
    onMarkAsRead: () -> Unit,
) {
    val spacing = IAMSThemeTokens.spacing

    val cardModifier = if (!notification.read && !isMarkingRead) {
        Modifier.fillMaxWidth()
    } else {
        Modifier.fillMaxWidth()
    }

    IAMSCard(
        onClick = if (!notification.read && !isMarkingRead) onMarkAsRead else null,
        modifier = if (!notification.read) {
            Modifier.background(Secondary)
        } else {
            Modifier
        },
    ) {
        Row(
            verticalAlignment = Alignment.Top,
            modifier = Modifier.fillMaxWidth(),
        ) {
            // Type icon
            NotificationTypeIcon(type = notification.type)

            Spacer(modifier = Modifier.width(spacing.md))

            // Text content
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = notification.title,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(modifier = Modifier.height(spacing.xs))
                Text(
                    text = notification.message,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary,
                )
                Spacer(modifier = Modifier.height(spacing.sm))
                Text(
                    text = notificationTimeAgo(notification.timestamp),
                    style = MaterialTheme.typography.bodySmall,
                    color = TextTertiary,
                )
            }

            // Unread dot or loading spinner
            if (!notification.read && !isMarkingRead) {
                Box(
                    modifier = Modifier
                        .padding(start = spacing.sm, top = spacing.xs)
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(Primary),
                )
            }
            if (isMarkingRead) {
                CircularProgressIndicator(
                    modifier = Modifier
                        .padding(start = spacing.sm)
                        .size(16.dp),
                    strokeWidth = 2.dp,
                    color = TextTertiary,
                )
            }
        }
    }
}

@Composable
private fun NotificationTypeIcon(type: String) {
    when (type.lowercase()) {
        "success" -> Icon(
            Icons.Default.CheckCircle,
            contentDescription = null,
            modifier = Modifier.size(24.dp),
            tint = PresentFg,
        )
        "warning" -> Icon(
            Icons.Default.Warning,
            contentDescription = null,
            modifier = Modifier.size(24.dp),
            tint = LateFg,
        )
        "info" -> Icon(
            Icons.Default.Info,
            contentDescription = null,
            modifier = Modifier.size(24.dp),
            tint = InfoFg,
        )
        else -> Icon(
            Icons.Default.Notifications,
            contentDescription = null,
            modifier = Modifier.size(24.dp),
            tint = TextTertiary,
        )
    }
}

@Composable
private fun NotificationsEmptyState() {
    val spacing = IAMSThemeTokens.spacing

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            Icons.Default.Notifications,
            contentDescription = null,
            modifier = Modifier.size(48.dp),
            tint = TextTertiary,
        )
        Spacer(modifier = Modifier.height(spacing.lg))
        Text(
            text = "No notifications",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = TextAlign.Center,
        )
        Spacer(modifier = Modifier.height(spacing.sm))
        Text(
            text = "You're all caught up!",
            style = MaterialTheme.typography.bodySmall,
            color = TextTertiary,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun NotificationsErrorState(onRetry: () -> Unit) {
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
            text = "Unable to load notifications. Please try again.",
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
private fun notificationTimeAgo(timestamp: String): String {
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
