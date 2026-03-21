package com.iams.app.ui.student

import androidx.compose.foundation.background
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
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Warning
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.NotificationResponse
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.InfoFg
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import java.time.Duration
import java.time.Instant
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudentNotificationsScreen(
    navController: NavController,
    viewModel: StudentNotificationsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        IAMSHeader(
            title = "Notifications",
            onBack = { navController.popBackStack() }
        )

        // Error state (no notifications loaded)
        if (uiState.error != null && !uiState.isRefreshing && uiState.notifications.isEmpty()) {
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
                        text = "Unable to load notifications. Please try again.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextSecondary,
                        textAlign = TextAlign.Center
                    )

                    Spacer(modifier = Modifier.height(spacing.lg))

                    IAMSButton(
                        text = "Retry",
                        onClick = { viewModel.loadNotifications() },
                        variant = IAMSButtonVariant.SECONDARY,
                        size = IAMSButtonSize.MD,
                        fullWidth = false
                    )
                }
            }
            return@Column
        }

        // Loading state
        if (uiState.isLoading && uiState.notifications.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = Primary)
            }
            return@Column
        }

        // Main content with pull-to-refresh
        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize()
        ) {
            if (uiState.notifications.isEmpty()) {
                // Empty state
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(vertical = 96.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Icon(
                        Icons.Outlined.Notifications,
                        contentDescription = null,
                        modifier = Modifier.size(48.dp),
                        tint = TextTertiary
                    )

                    Spacer(modifier = Modifier.height(spacing.lg))

                    Text(
                        text = "No notifications",
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextSecondary,
                        textAlign = TextAlign.Center
                    )

                    Spacer(modifier = Modifier.height(spacing.sm))

                    Text(
                        text = "You're all caught up!",
                        style = MaterialTheme.typography.bodyMedium,
                        color = TextTertiary,
                        textAlign = TextAlign.Center
                    )
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(spacing.screenPadding),
                    verticalArrangement = Arrangement.spacedBy(spacing.md)
                ) {
                    items(
                        items = uiState.notifications,
                        key = { it.id }
                    ) { notification ->
                        NotificationItem(
                            notification = notification,
                            isMarkingRead = uiState.markingReadIds.contains(notification.id),
                            onMarkAsRead = { viewModel.markAsRead(notification.id) }
                        )
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
    onMarkAsRead: () -> Unit
) {
    val spacing = IAMSThemeTokens.spacing
    val iconInfo = getNotificationIcon(notification.type)

    val cardModifier = if (!notification.read && !isMarkingRead) {
        Modifier.clickable { onMarkAsRead() }
    } else {
        Modifier
    }

    IAMSCard(
        modifier = cardModifier
    ) {
        // Apply unread background if needed
        val contentModifier = if (!notification.read) {
            Modifier
                .fillMaxWidth()
                .background(Secondary)
        } else {
            Modifier.fillMaxWidth()
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.Top
        ) {
            // Icon
            Icon(
                iconInfo.icon,
                contentDescription = null,
                modifier = Modifier
                    .size(24.dp)
                    .padding(end = 0.dp),
                tint = iconInfo.color
            )

            Spacer(modifier = Modifier.width(spacing.md))

            // Text content
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = notification.title,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(bottom = spacing.xs)
                )

                Text(
                    text = notification.message,
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary,
                    modifier = Modifier.padding(bottom = spacing.sm)
                )

                Text(
                    text = formatTimeAgo(notification.timestamp),
                    style = MaterialTheme.typography.bodySmall,
                    color = TextTertiary
                )
            }

            // Unread dot or loading
            if (!notification.read && !isMarkingRead) {
                Spacer(modifier = Modifier.width(spacing.sm))
                Box(
                    modifier = Modifier
                        .padding(top = spacing.xs)
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(Primary)
                )
            }

            if (isMarkingRead) {
                Spacer(modifier = Modifier.width(spacing.sm))
                CircularProgressIndicator(
                    modifier = Modifier
                        .size(16.dp)
                        .padding(top = spacing.xs),
                    color = TextTertiary,
                    strokeWidth = 2.dp
                )
            }
        }
    }
}

// --- Helpers ---

private data class NotificationIconInfo(
    val icon: ImageVector,
    val color: Color
)

private fun getNotificationIcon(type: String): NotificationIconInfo {
    return when (type) {
        "success" -> NotificationIconInfo(
            icon = Icons.Outlined.CheckCircle,
            color = PresentFg
        )
        "warning" -> NotificationIconInfo(
            icon = Icons.Outlined.Warning,
            color = LateFg
        )
        "info" -> NotificationIconInfo(
            icon = Icons.Outlined.Info,
            color = InfoFg
        )
        else -> NotificationIconInfo(
            icon = Icons.Outlined.Info,
            color = InfoFg
        )
    }
}

private fun formatTimeAgo(timestamp: String): String {
    return try {
        val instant = try {
            Instant.parse(timestamp)
        } catch (e: Exception) {
            ZonedDateTime.parse(timestamp, DateTimeFormatter.ISO_ZONED_DATE_TIME).toInstant()
        }

        val now = Instant.now()
        val duration = Duration.between(instant, now)

        when {
            duration.toMinutes() < 1 -> "Just now"
            duration.toMinutes() < 60 -> "${duration.toMinutes()}m ago"
            duration.toHours() < 24 -> "${duration.toHours()}h ago"
            duration.toDays() < 7 -> "${duration.toDays()}d ago"
            duration.toDays() < 30 -> "${duration.toDays() / 7}w ago"
            else -> "${duration.toDays() / 30}mo ago"
        }
    } catch (e: Exception) {
        timestamp
    }
}
