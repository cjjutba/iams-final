package com.iams.app.ui.faculty

import androidx.compose.foundation.background
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.StudentAttendanceStatus
import com.iams.app.ui.components.CardSkeleton
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.components.SkeletonBox
import com.iams.app.ui.components.TextSkeleton
import com.iams.app.ui.theme.AbsentBg
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.EarlyLeaveBg
import com.iams.app.ui.theme.EarlyLeaveFg
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.LateBg
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.PresentBg
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import java.time.LocalDate
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultyClassDetailScreen(
    navController: NavController,
    viewModel: FacultyClassDetailViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing

    // Format the date for header title
    val headerTitle = try {
        val parsed = LocalDate.parse(viewModel.date.take(10))
        parsed.format(DateTimeFormatter.ofPattern("MMM d, yyyy"))
    } catch (_: Exception) {
        "Class Detail"
    }

    Column(modifier = Modifier.fillMaxSize()) {
        IAMSHeader(
            title = headerTitle,
            onBack = { navController.popBackStack() }
        )

        // Error state (no data)
        if (uiState.error != null && uiState.classData == null) {
            ErrorState(
                onRetry = { viewModel.loadClassDetails() }
            )
            return
        }

        // Loading state (no data)
        if (uiState.isLoading && uiState.classData == null) {
            LoadingState()
            return
        }

        // Main content
        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize(),
        ) {
            LazyColumn(
                contentPadding = PaddingValues(
                    start = spacing.lg,
                    end = spacing.lg,
                    bottom = spacing.xxl,
                ),
                modifier = Modifier.fillMaxSize(),
            ) {
                // Class info card
                item {
                    Spacer(modifier = Modifier.height(spacing.lg))
                    uiState.classData?.let { data ->
                        IAMSCard {
                            Text(
                                text = data.subjectName ?: "",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.SemiBold,
                            )
                            if (!data.subjectCode.isNullOrBlank()) {
                                Spacer(modifier = Modifier.height(spacing.xs))
                                Text(
                                    text = data.subjectCode,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextSecondary,
                                )
                            }
                            Spacer(modifier = Modifier.height(spacing.sm))
                            Text(
                                text = "${data.startTime ?: ""} - ${data.endTime ?: ""}",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextTertiary,
                            )
                        }
                    }
                    Spacer(modifier = Modifier.height(spacing.md))
                }

                // Summary card
                item {
                    IAMSCard {
                        Text(
                            text = "Attendance Summary",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Spacer(modifier = Modifier.height(spacing.lg))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceAround,
                        ) {
                            StatItem(
                                label = "Present",
                                value = uiState.presentCount,
                                color = PresentFg,
                            )
                            StatItem(
                                label = "Late",
                                value = uiState.lateCount,
                                color = LateFg,
                            )
                            StatItem(
                                label = "Absent",
                                value = uiState.absentCount,
                                color = AbsentFg,
                            )
                            StatItem(
                                label = "Left",
                                value = uiState.earlyLeaveCount,
                                color = EarlyLeaveFg,
                            )
                        }
                    }
                    Spacer(modifier = Modifier.height(spacing.lg))
                }

                // Section title
                item {
                    Text(
                        text = "Students (${uiState.students.size})",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                }

                // Student list
                if (uiState.students.isEmpty()) {
                    item {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 48.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Text(
                                text = "No students enrolled",
                                style = MaterialTheme.typography.bodyLarge,
                                color = TextSecondary,
                                textAlign = TextAlign.Center,
                            )
                        }
                    }
                } else {
                    items(uiState.students, key = { it.studentId }) { student ->
                        StudentCard(
                            student = student,
                            onClick = {
                                navController.navigate(
                                    "studentDetail/${student.studentId}/${viewModel.scheduleId}"
                                )
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
private fun StatItem(
    label: String,
    value: Int,
    color: androidx.compose.ui.graphics.Color,
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = value.toString(),
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
private fun StudentCard(
    student: StudentAttendanceStatus,
    onClick: () -> Unit,
) {
    val spacing = IAMSThemeTokens.spacing
    val nameParts = student.studentName.split(" ", limit = 2)
    val firstInitial = nameParts.getOrNull(0)?.firstOrNull()?.uppercaseChar() ?: ' '
    val lastInitial = nameParts.getOrNull(1)?.firstOrNull()?.uppercaseChar() ?: ' '

    IAMSCard(onClick = onClick) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            // Avatar
            Box(
                contentAlignment = Alignment.Center,
                modifier = Modifier
                    .size(40.dp)
                    .clip(CircleShape)
                    .background(Secondary),
            ) {
                Text(
                    text = "$firstInitial$lastInitial",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                    color = TextPrimary,
                )
            }

            Spacer(modifier = Modifier.width(spacing.md))

            // Info
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = student.studentName,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = student.studentNumber ?: student.studentId,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary,
                )
            }

            Spacer(modifier = Modifier.width(spacing.md))

            // Status badge
            StatusBadge(status = student.status)
        }
    }
}

@Composable
private fun StatusBadge(status: String) {
    val (bg, fg, label) = when (status.lowercase()) {
        "present" -> Triple(PresentBg, PresentFg, "Present")
        "late" -> Triple(LateBg, LateFg, "Late")
        "absent" -> Triple(AbsentBg, AbsentFg, "Absent")
        "early_leave" -> Triple(EarlyLeaveBg, EarlyLeaveFg, "Left Early")
        else -> Triple(Secondary, TextSecondary, status.replaceFirstChar { it.uppercase() })
    }

    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(9999.dp))
            .background(bg)
            .padding(horizontal = 8.dp, vertical = 4.dp),
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.SemiBold,
            color = fg,
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
            text = "Unable to load class details. Please try again.",
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

@Composable
private fun LoadingState() {
    val spacing = IAMSThemeTokens.spacing

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(spacing.lg),
    ) {
        Spacer(modifier = Modifier.height(spacing.lg))
        // Class info skeleton
        IAMSCard {
            SkeletonBox(width = 200.dp, height = 20.dp)
            Spacer(modifier = Modifier.height(spacing.sm))
            TextSkeleton(width = 100.dp)
            Spacer(modifier = Modifier.height(spacing.sm))
            TextSkeleton(width = 140.dp)
        }
        Spacer(modifier = Modifier.height(spacing.md))
        // Summary skeleton
        IAMSCard {
            SkeletonBox(width = 160.dp, height = 18.dp)
            Spacer(modifier = Modifier.height(spacing.lg))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceAround,
            ) {
                repeat(4) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        SkeletonBox(width = 32.dp, height = 24.dp)
                        Spacer(modifier = Modifier.height(spacing.xs))
                        TextSkeleton(width = 40.dp, height = 12.dp)
                    }
                }
            }
        }
        Spacer(modifier = Modifier.height(spacing.lg))
        // Student list skeletons
        TextSkeleton(width = 120.dp, height = 18.dp)
        Spacer(modifier = Modifier.height(spacing.lg))
        repeat(3) {
            CardSkeleton()
            Spacer(modifier = Modifier.height(spacing.sm))
        }
    }
}
