package com.iams.app.ui.student

import androidx.compose.foundation.BorderStroke
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.AttendanceRecordResponse
import com.iams.app.data.model.ScheduleResponse
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
import com.iams.app.ui.components.AttendanceStatus
import com.iams.app.ui.components.CardSkeleton
import com.iams.app.ui.components.IAMSBadge
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudentHomeScreen(
    navController: NavController,
    viewModel: StudentHomeViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing
    val toastState = LocalToastState.current

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            toastState.showToast(it, ToastType.ERROR)
            viewModel.clearError()
        }
    }

    // Error state with no cached data
    if (uiState.error != null && uiState.todaySchedules.isEmpty() && !uiState.isLoading) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(Background)
        ) {
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
                        text = "Unable to load your schedule. Please try again.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextSecondary,
                        textAlign = TextAlign.Center
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                    IAMSButton(
                        text = "Retry",
                        onClick = {
                            viewModel.clearError()
                            viewModel.loadData()
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

    PullToRefreshBox(
        isRefreshing = uiState.isRefreshing,
        onRefresh = { viewModel.refresh() },
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = spacing.lg),
        ) {
            // ── Header content ──
            item {
                Spacer(modifier = Modifier.height(spacing.lg))

                // Greeting row with notification bell
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "${viewModel.getGreeting()}, ${uiState.user?.firstName ?: "Student"}!",
                        style = MaterialTheme.typography.headlineLarge,
                        fontWeight = FontWeight.Bold,
                        color = Primary,
                        modifier = Modifier.weight(1f)
                    )
                    IconButton(onClick = { navController.navigate(Routes.STUDENT_NOTIFICATIONS) }) {
                        Icon(
                            Icons.Default.Notifications,
                            contentDescription = "Notifications",
                            modifier = Modifier.size(24.dp),
                            tint = TextPrimary
                        )
                    }
                }

                Spacer(modifier = Modifier.height(spacing.sm))

                // Date
                val today = LocalDate.now()
                val dateFormatter = DateTimeFormatter.ofPattern(
                    "EEEE, MMMM d, yyyy", Locale.getDefault()
                )
                Text(
                    text = today.format(dateFormatter),
                    style = MaterialTheme.typography.bodyLarge,
                    color = TextSecondary
                )

                Spacer(modifier = Modifier.height(spacing.xxl))

                // Loading skeleton placeholders
                if (uiState.isLoading) {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    CardSkeleton()
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    CardSkeleton()
                }

                // Face status card
                if (!uiState.isLoading) {
                    FaceStatusCard(
                        faceRegistered = uiState.faceRegistered,
                        onRegisterClick = {
                            navController.navigate(Routes.studentFaceRegister("register"))
                        }
                    )
                }

                Spacer(modifier = Modifier.height(spacing.xxl))

                // Current class card
                if (!uiState.isLoading && uiState.currentClass != null) {
                    CurrentClassCard(schedule = uiState.currentClass!!)
                    Spacer(modifier = Modifier.height(spacing.xxl))
                }

                // Upcoming class card (only when no current class)
                if (!uiState.isLoading && uiState.currentClass == null && uiState.nextClass != null) {
                    UpcomingClassCard(schedule = uiState.nextClass!!)
                    Spacer(modifier = Modifier.height(spacing.xxl))
                }

                // Section title
                Text(
                    text = "Today's Classes",
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = Primary
                )
                Spacer(modifier = Modifier.height(spacing.lg))
            }

            // ── Loading skeleton for schedule cards ──
            if (uiState.isLoading) {
                items(3) {
                    CardSkeleton()
                    Spacer(modifier = Modifier.height(spacing.sm))
                }
            }

            // ── Today's schedule cards ──
            if (!uiState.isLoading && uiState.todaySchedules.isNotEmpty()) {
                items(uiState.todaySchedules, key = { it.id }) { schedule ->
                    TodayScheduleCard(schedule = schedule)
                    Spacer(modifier = Modifier.height(spacing.sm))
                }
            }

            // ── Empty state ──
            if (uiState.todaySchedules.isEmpty() && !uiState.isLoading) {
                item {
                    EmptyScheduleState(viewModel = viewModel)
                }
            }

            // ── Recent activity ──
            if (uiState.recentActivity.isNotEmpty()) {
                item {
                    Spacer(modifier = Modifier.height(spacing.xxl))
                    Text(
                        text = "Recent Activity",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = Primary
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                }

                items(uiState.recentActivity, key = { it.id }) { record ->
                    ActivityFeedItem(
                        record = record,
                        viewModel = viewModel
                    )
                    Spacer(modifier = Modifier.height(spacing.sm))
                }
            }

            // Bottom spacing
            item {
                Spacer(modifier = Modifier.height(spacing.xxl))
            }
        }
    }
}

// ── Face Status Card ──

@Composable
private fun FaceStatusCard(
    faceRegistered: Boolean?,
    onRegisterClick: () -> Unit = {},
) {
    val spacing = IAMSThemeTokens.spacing

    // Still loading
    if (faceRegistered == null) return

    IAMSCard(
        onClick = if (!faceRegistered) onRegisterClick else null
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = if (faceRegistered) Icons.Default.CheckCircle else Icons.Default.Warning,
                contentDescription = null,
                modifier = Modifier.size(20.dp),
                tint = if (faceRegistered) PresentFg else AbsentFg
            )
            Spacer(modifier = Modifier.width(spacing.md))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = if (faceRegistered) "Face Registered" else "Face Not Registered",
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = if (faceRegistered) PresentFg else AbsentFg
                )
                Text(
                    text = if (faceRegistered) {
                        "Your face is registered for attendance"
                    } else {
                        "Register your face to enable attendance tracking"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
            }
        }
    }
}

// ── Current Class Card ──

@Composable
private fun CurrentClassCard(schedule: ScheduleResponse) {
    val spacing = IAMSThemeTokens.spacing
    val radius = IAMSThemeTokens.radius

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = radius.cardShape,
        color = Background,
        border = BorderStroke(1.dp, Border),
        shadowElevation = 0.dp,
    ) {
        Column(modifier = Modifier.padding(spacing.cardPadding)) {
            Text(
                text = "CURRENT CLASS",
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.SemiBold,
                color = Primary,
                letterSpacing = 0.5.sp
            )
            Spacer(modifier = Modifier.height(spacing.xs))
            Text(
                text = schedule.subjectName,
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.SemiBold,
                color = Primary
            )
            Spacer(modifier = Modifier.height(spacing.xs))
            Text(
                text = buildString {
                    if (!schedule.roomName.isNullOrBlank()) {
                        append(schedule.roomName)
                        append(" \u2022 ")
                    }
                    append("Ongoing")
                },
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary
            )
        }
    }
}

// ── Upcoming Class Card ──

@Composable
private fun UpcomingClassCard(schedule: ScheduleResponse) {
    val spacing = IAMSThemeTokens.spacing
    val radius = IAMSThemeTokens.radius

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = radius.cardShape,
        color = Background,
        border = BorderStroke(1.dp, Border),
        shadowElevation = 0.dp,
    ) {
        Column(modifier = Modifier.padding(spacing.cardPadding)) {
            Text(
                text = "UPCOMING CLASS",
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.SemiBold,
                color = TextSecondary,
                letterSpacing = 0.5.sp
            )
            Spacer(modifier = Modifier.height(spacing.xs))
            Text(
                text = schedule.subjectName,
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.SemiBold,
                color = Primary
            )
            Spacer(modifier = Modifier.height(spacing.xs))
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
        }
    }
}

// ── Today Schedule Card ──

@Composable
private fun TodayScheduleCard(schedule: ScheduleResponse) {
    val spacing = IAMSThemeTokens.spacing

    IAMSCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            // Subject code
            if (!schedule.subjectCode.isNullOrBlank()) {
                Text(
                    text = schedule.subjectCode,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextTertiary
                )
                Spacer(modifier = Modifier.height(spacing.xs))
            }

            // Subject name
            Text(
                text = schedule.subjectName,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.SemiBold,
                color = Primary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )

            Spacer(modifier = Modifier.height(spacing.sm))

            // Time and room
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
        }
    }
}

// ── Empty Schedule State ──

@Composable
private fun EmptyScheduleState(viewModel: StudentHomeViewModel) {
    val spacing = IAMSThemeTokens.spacing
    val radius = IAMSThemeTokens.radius
    val nextDay = viewModel.getNextDayWithClasses()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = spacing.xxxl),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "No classes scheduled for today",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = TextAlign.Center
        )

        if (nextDay != null) {
            Spacer(modifier = Modifier.height(spacing.lg))
            Text(
                text = "Next classes on ${getDayName(nextDay.first)}",
                style = MaterialTheme.typography.bodyMedium,
                color = TextTertiary,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(spacing.sm))

            val previewSchedules = nextDay.second.take(3)
            previewSchedules.forEach { schedule ->
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = spacing.sm),
                    shape = radius.cardShape,
                    color = Background,
                    border = BorderStroke(1.dp, Border),
                    shadowElevation = 0.dp,
                ) {
                    Column(
                        modifier = Modifier.padding(
                            horizontal = spacing.cardPadding,
                            vertical = spacing.sm
                        )
                    ) {
                        Text(
                            text = schedule.subjectName,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = Primary,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
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
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary
                        )
                    }
                }
            }

            if (nextDay.second.size > 3) {
                Spacer(modifier = Modifier.height(spacing.sm))
                Text(
                    text = "+${nextDay.second.size - 3} more",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextTertiary,
                    textAlign = TextAlign.Center
                )
            }
        }

        if (nextDay == null && viewModel.uiState.value.allSchedules.isEmpty()) {
            Spacer(modifier = Modifier.height(spacing.sm))
            Text(
                text = "You haven't been enrolled in any classes yet",
                style = MaterialTheme.typography.bodyMedium,
                color = TextTertiary,
                textAlign = TextAlign.Center
            )
        }
    }
}

// ── Activity Feed Item ──

@Composable
private fun ActivityFeedItem(
    record: AttendanceRecordResponse,
    viewModel: StudentHomeViewModel
) {
    val spacing = IAMSThemeTokens.spacing
    val (subjectName, subjectCode) = viewModel.getScheduleInfoForRecord(record)
    val status = parseStatus(record.status)

    IAMSCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                if (subjectCode.isNotBlank()) {
                    Text(
                        text = subjectCode,
                        style = MaterialTheme.typography.bodySmall,
                        color = TextTertiary
                    )
                    Spacer(modifier = Modifier.height(spacing.xs))
                }
                Text(
                    text = subjectName,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = Primary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Spacer(modifier = Modifier.height(spacing.xs))
                Text(
                    text = formatDateDisplay(record.date),
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
            }
            Spacer(modifier = Modifier.width(spacing.sm))
            IAMSBadge(status = status)
        }
    }
}

// ── Utility functions ──

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

/**
 * Format "YYYY-MM-DD" to "MMM dd, yyyy"
 */
private fun formatDateDisplay(date: String): String {
    return try {
        val localDate = LocalDate.parse(date)
        localDate.format(DateTimeFormatter.ofPattern("MMM dd, yyyy", Locale.getDefault()))
    } catch (_: Exception) {
        date
    }
}

/**
 * Convert backend day number (0=Monday) to full name.
 */
private fun getDayName(backendDay: Int): String {
    val days = listOf("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    return days.getOrElse(backendDay) { "" }
}

/**
 * Parse status string to AttendanceStatus enum.
 */
private fun parseStatus(status: String): AttendanceStatus {
    return when (status.lowercase()) {
        "present" -> AttendanceStatus.PRESENT
        "late" -> AttendanceStatus.LATE
        "absent" -> AttendanceStatus.ABSENT
        "early_leave" -> AttendanceStatus.EARLY_LEAVE
        else -> AttendanceStatus.ABSENT
    }
}
