package com.iams.app.ui.student

import androidx.compose.animation.animateColorAsState
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
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.DoneAll
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Warning
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.rememberSwipeToDismissBoxState
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.NotificationResponse
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.theme.Background
import com.iams.app.ui.components.SkeletonBox
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.InfoFg
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
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
    var showMenu by remember { mutableStateOf(false) }

    val unreadNotifications = uiState.notifications.filter { !it.read }
    val readNotifications = uiState.notifications.filter { it.read }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        // Header with overflow menu
        IAMSHeader(
            title = "Notifications",
            onBack = { navController.popBackStack() },
            trailing = {
                if (uiState.notifications.isNotEmpty()) {
                    Box {
                        IconButton(onClick = { showMenu = true }) {
                            Icon(
                                Icons.Outlined.MoreVert,
                                contentDescription = "More options",
                                modifier = Modifier.size(22.dp),
                                tint = TextPrimary
                            )
                        }
                        DropdownMenu(
                            expanded = showMenu,
                            onDismissRequest = { showMenu = false }
                        ) {
                            if (viewModel.hasUnread) {
                                DropdownMenuItem(
                                    text = { Text("Mark all as read") },
                                    onClick = {
                                        showMenu = false
                                        viewModel.markAllAsRead()
                                    },
                                    leadingIcon = {
                                        Icon(
                                            Icons.Outlined.DoneAll,
                                            contentDescription = null,
                                            modifier = Modifier.size(20.dp)
                                        )
                                    }
                                )
                            }
                            DropdownMenuItem(
                                text = { Text("Delete all", color = Color(0xFFDC2626)) },
                                onClick = {
                                    showMenu = false
                                    viewModel.deleteAllNotifications()
                                },
                                leadingIcon = {
                                    Icon(
                                        Icons.Outlined.Delete,
                                        contentDescription = null,
                                        modifier = Modifier.size(20.dp),
                                        tint = Color(0xFFDC2626)
                                    )
                                }
                            )
                        }
                    }
                }
            }
        )

        // Error state
        if (uiState.error != null && !uiState.isRefreshing && uiState.notifications.isEmpty()) {
            NotificationsErrorState(onRetry = { viewModel.loadNotifications() })
            return@Column
        }

        // Loading skeleton
        if (uiState.isLoading && uiState.notifications.isEmpty()) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = spacing.screenPadding)
                    .padding(top = spacing.md)
            ) {
                // Section header skeleton
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = spacing.sm),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    SkeletonBox(width = 60.dp, height = 14.dp)
                    SkeletonBox(width = 20.dp, height = 14.dp)
                }
                // 5 notification item skeletons
                repeat(5) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(vertical = spacing.md),
                        verticalAlignment = Alignment.Top
                    ) {
                        SkeletonBox(width = 36.dp, height = 36.dp, cornerRadius = 18.dp)
                        Spacer(modifier = Modifier.width(spacing.md))
                        Column(modifier = Modifier.weight(1f)) {
                            SkeletonBox(width = 160.dp, height = 14.dp)
                            Spacer(modifier = Modifier.height(4.dp))
                            SkeletonBox(height = 12.dp)
                            Spacer(modifier = Modifier.height(4.dp))
                            SkeletonBox(width = 60.dp, height = 10.dp)
                        }
                    }
                    HorizontalDivider(color = Border, thickness = 0.5.dp)
                }
            }
            return@Column
        }

        // Main content
        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize()
        ) {
            if (uiState.notifications.isEmpty()) {
                NotificationsEmptyState()
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(
                        start = spacing.screenPadding,
                        end = spacing.screenPadding,
                        top = spacing.md,
                        bottom = spacing.xxl
                    )
                ) {
                    // Unread section
                    if (unreadNotifications.isNotEmpty()) {
                        item(key = "unread_header") {
                            SectionHeader(
                                title = "Unread",
                                count = unreadNotifications.size
                            )
                        }
                        items(
                            items = unreadNotifications,
                            key = { "unread_${it.id}" }
                        ) { notification ->
                            SwipeableNotificationItem(
                                notification = notification,
                                isMarkingRead = uiState.markingReadIds.contains(notification.id),
                                onMarkAsRead = { viewModel.markAsRead(notification.id) },
                                onDelete = { viewModel.deleteNotification(notification.id) }
                            )
                        }
                    }

                    // Read section
                    if (readNotifications.isNotEmpty()) {
                        item(key = "read_header") {
                            if (unreadNotifications.isNotEmpty()) {
                                Spacer(modifier = Modifier.height(spacing.lg))
                            }
                            SectionHeader(
                                title = "Read",
                                count = readNotifications.size
                            )
                        }
                        items(
                            items = readNotifications,
                            key = { "read_${it.id}" }
                        ) { notification ->
                            SwipeableNotificationItem(
                                notification = notification,
                                isMarkingRead = false,
                                onMarkAsRead = {},
                                onDelete = { viewModel.deleteNotification(notification.id) }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SectionHeader(title: String, count: Int) {
    val spacing = IAMSThemeTokens.spacing

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = spacing.sm),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
            color = TextSecondary
        )
        Text(
            text = count.toString(),
            style = MaterialTheme.typography.bodySmall,
            color = TextTertiary
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SwipeableNotificationItem(
    notification: NotificationResponse,
    isMarkingRead: Boolean,
    onMarkAsRead: () -> Unit,
    onDelete: () -> Unit
) {
    val spacing = IAMSThemeTokens.spacing
    val dismissState = rememberSwipeToDismissBoxState(
        confirmValueChange = { value ->
            when (value) {
                SwipeToDismissBoxValue.EndToStart -> {
                    onDelete()
                    true
                }
                SwipeToDismissBoxValue.StartToEnd -> {
                    if (!notification.read) onMarkAsRead()
                    true
                }
                SwipeToDismissBoxValue.Settled -> false
            }
        }
    )

    // Reset state if notification was updated (marked as read)
    LaunchedEffect(notification.read) {
        if (notification.read && dismissState.currentValue == SwipeToDismissBoxValue.StartToEnd) {
            dismissState.snapTo(SwipeToDismissBoxValue.Settled)
        }
    }

    SwipeToDismissBox(
        state = dismissState,
        backgroundContent = {
            val direction = dismissState.dismissDirection

            val bgColor by animateColorAsState(
                targetValue = when (direction) {
                    SwipeToDismissBoxValue.EndToStart -> Color(0xFFFEE2E2)
                    SwipeToDismissBoxValue.StartToEnd -> if (!notification.read) Color(0xFFDCFCE7) else Color.Transparent
                    else -> Color.Transparent
                },
                label = "swipeBg"
            )

            val iconTint = when (direction) {
                SwipeToDismissBoxValue.EndToStart -> Color(0xFFDC2626)
                SwipeToDismissBoxValue.StartToEnd -> PresentFg
                else -> Color.Transparent
            }

            val icon = when (direction) {
                SwipeToDismissBoxValue.EndToStart -> Icons.Outlined.Delete
                SwipeToDismissBoxValue.StartToEnd -> Icons.Outlined.DoneAll
                else -> Icons.Outlined.Delete
            }

            val alignment = when (direction) {
                SwipeToDismissBoxValue.EndToStart -> Alignment.CenterEnd
                SwipeToDismissBoxValue.StartToEnd -> Alignment.CenterStart
                else -> Alignment.CenterEnd
            }

            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(bgColor)
                    .padding(horizontal = spacing.xl),
                contentAlignment = alignment
            ) {
                Icon(
                    icon,
                    contentDescription = null,
                    modifier = Modifier.size(22.dp),
                    tint = iconTint
                )
            }
        },
        enableDismissFromStartToEnd = !notification.read,
        enableDismissFromEndToStart = true
    ) {
        NotificationItemContent(
            notification = notification,
            isMarkingRead = isMarkingRead,
            onMarkAsRead = onMarkAsRead
        )
    }
}

@Composable
private fun NotificationItemContent(
    notification: NotificationResponse,
    isMarkingRead: Boolean,
    onMarkAsRead: () -> Unit
) {
    val spacing = IAMSThemeTokens.spacing
    val iconInfo = getNotificationIcon(notification.type)

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Background)
            .then(
                if (!notification.read && !isMarkingRead)
                    Modifier.clickable { onMarkAsRead() }
                else Modifier
            )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = spacing.md),
            verticalAlignment = Alignment.Top
        ) {
            // Type icon
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(if (!notification.read) iconInfo.color.copy(alpha = 0.1f) else Secondary),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    iconInfo.icon,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                    tint = if (!notification.read) iconInfo.color else TextTertiary
                )
            }

            Spacer(modifier = Modifier.width(spacing.md))

            // Text content
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = notification.title,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = if (!notification.read) FontWeight.SemiBold else FontWeight.Normal,
                    color = if (!notification.read) TextPrimary else TextSecondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )

                Spacer(modifier = Modifier.height(2.dp))

                Text(
                    text = notification.message,
                    style = MaterialTheme.typography.bodySmall,
                    color = if (!notification.read) TextSecondary else TextTertiary,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )

                Spacer(modifier = Modifier.height(spacing.xs))

                Text(
                    text = formatTimeAgo(notification.createdAt),
                    style = MaterialTheme.typography.labelSmall,
                    color = TextTertiary
                )
            }

            Spacer(modifier = Modifier.width(spacing.sm))

            // Unread indicator (red dot) or loading
            if (!notification.read && !isMarkingRead) {
                Box(
                    modifier = Modifier
                        .padding(top = spacing.sm)
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(Color(0xFFDC2626))
                )
            }

            if (isMarkingRead) {
                CircularProgressIndicator(
                    modifier = Modifier
                        .padding(top = spacing.xs)
                        .size(14.dp),
                    color = TextTertiary,
                    strokeWidth = 1.5.dp
                )
            }
        }

        // Divider
        HorizontalDivider(
            color = Border,
            thickness = 0.5.dp
        )
    }
}

// --- Empty / Error states ---

@Composable
private fun NotificationsEmptyState() {
    val spacing = IAMSThemeTokens.spacing

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
            fontWeight = FontWeight.Medium,
            color = TextSecondary,
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(spacing.xs))

        Text(
            text = "You're all caught up!",
            style = MaterialTheme.typography.bodySmall,
            color = TextTertiary,
            textAlign = TextAlign.Center
        )
    }
}

@Composable
private fun NotificationsErrorState(onRetry: () -> Unit) {
    val spacing = IAMSThemeTokens.spacing

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
                text = "Unable to load notifications",
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
                color = TextSecondary,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(spacing.sm))

            Text(
                text = "Please check your connection and try again.",
                style = MaterialTheme.typography.bodySmall,
                color = TextTertiary,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(spacing.lg))

            IAMSButton(
                text = "Retry",
                onClick = onRetry,
                variant = IAMSButtonVariant.SECONDARY,
                size = IAMSButtonSize.MD,
                fullWidth = false
            )
        }
    }
}

// --- Helpers ---

private data class NotificationIconInfo(
    val icon: ImageVector,
    val color: Color
)

private fun getNotificationIcon(type: String): NotificationIconInfo {
    return when (type.lowercase()) {
        "check_in" -> NotificationIconInfo(
            icon = Icons.Outlined.CheckCircle,
            color = PresentFg
        )
        "early_leave" -> NotificationIconInfo(
            icon = Icons.Outlined.Warning,
            color = LateFg
        )
        "early_leave_return" -> NotificationIconInfo(
            icon = Icons.Outlined.CheckCircle,
            color = PresentFg
        )
        "broadcast" -> NotificationIconInfo(
            icon = Icons.Outlined.Notifications,
            color = InfoFg
        )
        "system" -> NotificationIconInfo(
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
    if (timestamp.isBlank()) return ""
    return try {
        val instant = try {
            Instant.parse(timestamp)
        } catch (_: Exception) {
            try {
                ZonedDateTime.parse(timestamp, DateTimeFormatter.ISO_ZONED_DATE_TIME).toInstant()
            } catch (_: Exception) {
                // Naive timestamp (no timezone) — treat as UTC (backend stores UTC)
                java.time.LocalDateTime.parse(timestamp.replace(" ", "T"))
                    .atZone(java.time.ZoneId.of("UTC"))
                    .toInstant()
            }
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
    } catch (_: Exception) {
        timestamp
    }
}
