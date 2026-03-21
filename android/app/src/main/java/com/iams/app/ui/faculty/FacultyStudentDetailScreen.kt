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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
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
import com.iams.app.data.model.AttendanceRecordResponse
import com.iams.app.ui.components.IAMSBadge
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.components.AttendanceStatus
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import java.time.LocalDate
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultyStudentDetailScreen(
    navController: NavController,
    viewModel: FacultyStudentDetailViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing
    val layout = IAMSThemeTokens.layout

    Column(modifier = Modifier.fillMaxSize()) {
        IAMSHeader(
            title = "Student Detail",
            onBack = { navController.popBackStack() }
        )

        // Error state (no data at all)
        if (uiState.error != null && !uiState.isRefreshing && uiState.student == null && uiState.summary == null) {
            ErrorState(onRetry = { viewModel.loadStudentDetails() })
            return
        }

        // Loading state
        if (uiState.isLoading && uiState.student == null) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center,
            ) {
                CircularProgressIndicator()
            }
            return
        }

        // Data state
        val student = uiState.student
        val summary = uiState.summary
        val displayName = if (student != null) "${student.firstName} ${student.lastName}" else viewModel.studentId
        val displayFirstInitial = student?.firstName?.firstOrNull()?.uppercaseChar() ?: ' '
        val displayLastInitial = student?.lastName?.firstOrNull()?.uppercaseChar() ?: ' '
        val displayStudentId = student?.studentId ?: viewModel.studentId

        val totalClasses = summary?.total ?: 0
        val present = summary?.present ?: 0
        val late = summary?.late ?: 0
        val absent = summary?.absent ?: 0
        val attendanceRate = summary?.attendanceRate ?: 0f

        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize(),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(
                        start = spacing.lg,
                        end = spacing.lg,
                        top = spacing.lg,
                        bottom = spacing.xxxl,
                    ),
            ) {
                // Student header
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = spacing.xxxl),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    // Avatar
                    Box(
                        contentAlignment = Alignment.Center,
                        modifier = Modifier
                            .size(layout.avatarXl)
                            .clip(CircleShape)
                            .background(Secondary),
                    ) {
                        Text(
                            text = "$displayFirstInitial$displayLastInitial",
                            style = MaterialTheme.typography.headlineLarge,
                            fontWeight = FontWeight.SemiBold,
                            color = TextPrimary,
                        )
                    }

                    Spacer(modifier = Modifier.height(spacing.lg))

                    Text(
                        text = displayName,
                        style = MaterialTheme.typography.headlineLarge,
                        fontWeight = FontWeight.Bold,
                        textAlign = TextAlign.Center,
                    )

                    Spacer(modifier = Modifier.height(spacing.sm))

                    Text(
                        text = displayStudentId,
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextSecondary,
                        textAlign = TextAlign.Center,
                    )

                    if (student?.email != null) {
                        Spacer(modifier = Modifier.height(spacing.xs))
                        Text(
                            text = student.email,
                            style = MaterialTheme.typography.bodySmall,
                            color = TextTertiary,
                            textAlign = TextAlign.Center,
                        )
                    }
                }

                // Overall stats card
                IAMSCard {
                    Text(
                        text = "Attendance Summary",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.SemiBold,
                    )

                    Spacer(modifier = Modifier.height(spacing.lg))

                    // Stats grid 2x2
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceAround,
                    ) {
                        StatCell(label = "Total Classes", value = totalClasses.toString())
                        StatCell(label = "Present", value = present.toString(), color = PresentFg)
                    }
                    Spacer(modifier = Modifier.height(spacing.lg))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceAround,
                    ) {
                        StatCell(label = "Late", value = late.toString(), color = LateFg)
                        StatCell(label = "Absent", value = absent.toString(), color = AbsentFg)
                    }

                    Spacer(modifier = Modifier.height(spacing.lg))
                    HorizontalDivider(thickness = 1.dp, color = Border)
                    Spacer(modifier = Modifier.height(spacing.md))

                    // Attendance rate
                    Column(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(
                            text = "Attendance Rate",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextTertiary,
                        )
                        Spacer(modifier = Modifier.height(spacing.xs))
                        Text(
                            text = "${String.format("%.1f", attendanceRate)}%",
                            style = MaterialTheme.typography.headlineMedium,
                            fontWeight = FontWeight.Bold,
                            color = when {
                                attendanceRate >= 80f -> PresentFg
                                attendanceRate >= 60f -> LateFg
                                else -> AbsentFg
                            },
                        )
                    }
                }

                Spacer(modifier = Modifier.height(spacing.xxl))

                // Recent attendance section
                Text(
                    text = "Recent Attendance",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold,
                )

                Spacer(modifier = Modifier.height(spacing.lg))

                if (uiState.recentRecords.isNotEmpty()) {
                    uiState.recentRecords.forEach { record ->
                        AttendanceRecordCard(record = record)
                        Spacer(modifier = Modifier.height(spacing.md))
                    }
                } else {
                    IAMSCard {
                        Text(
                            text = "No recent records",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun StatCell(
    label: String,
    value: String,
    color: androidx.compose.ui.graphics.Color = TextPrimary,
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.width(120.dp),
    ) {
        Text(
            text = value,
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = color,
        )
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = TextTertiary,
        )
    }
}

@Composable
private fun AttendanceRecordCard(record: AttendanceRecordResponse) {
    val spacing = IAMSThemeTokens.spacing
    val formattedDate = try {
        val parsed = LocalDate.parse(record.date.take(10))
        parsed.format(DateTimeFormatter.ofPattern("MMM d, yyyy"))
    } catch (_: Exception) {
        record.date
    }

    val badgeStatus = when (record.status.lowercase()) {
        "present" -> AttendanceStatus.PRESENT
        "late" -> AttendanceStatus.LATE
        "absent" -> AttendanceStatus.ABSENT
        "early_leave" -> AttendanceStatus.EARLY_LEAVE
        else -> AttendanceStatus.ABSENT
    }

    IAMSCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = formattedDate,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
            )
            IAMSBadge(status = badgeStatus)
        }

        if (!record.checkInTime.isNullOrBlank()) {
            Spacer(modifier = Modifier.height(spacing.sm))
            Text(
                text = "Check-in: ${record.checkInTime}",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary,
            )
        }

        if (record.presenceScore != null) {
            Spacer(modifier = Modifier.height(spacing.xs))
            Text(
                text = "Presence: ${String.format("%.1f", record.presenceScore)}%",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary,
            )
        }
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
            text = "Unable to load student details. Please try again.",
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
