package com.iams.app.ui.faculty

import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
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
import androidx.compose.material.icons.filled.Download
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.AttendanceSummaryResponse
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.SkeletonBox
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.EarlyLeaveFg
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultyReportsScreen(
    navController: NavController,
    viewModel: FacultyReportsViewModel = hiltViewModel()
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

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        IAMSHeader(
            title = "Reports",
            onBack = { navController.popBackStack() }
        )

        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize()
        ) {
            when {
                uiState.isLoading && uiState.schedules.isEmpty() -> {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .verticalScroll(rememberScrollState())
                            .padding(horizontal = spacing.screenPadding)
                            .padding(top = spacing.lg, bottom = spacing.xxxl),
                        verticalArrangement = Arrangement.spacedBy(spacing.lg)
                    ) {
                        // Generate Report card skeleton
                        IAMSCard {
                            SkeletonBox(width = 140.dp, height = 22.dp)
                            Spacer(modifier = Modifier.height(spacing.lg))
                            // Dropdown skeleton
                            SkeletonBox(width = 80.dp, height = 14.dp)
                            Spacer(modifier = Modifier.height(6.dp))
                            SkeletonBox(height = 48.dp, cornerRadius = 12.dp)
                            Spacer(modifier = Modifier.height(spacing.md))
                            // Report type skeleton
                            SkeletonBox(width = 80.dp, height = 14.dp)
                            Spacer(modifier = Modifier.height(6.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(spacing.sm)) {
                                SkeletonBox(width = 120.dp, height = 40.dp, cornerRadius = 8.dp, modifier = Modifier.weight(1f))
                                SkeletonBox(width = 120.dp, height = 40.dp, cornerRadius = 8.dp, modifier = Modifier.weight(1f))
                            }
                            Spacer(modifier = Modifier.height(spacing.lg))
                            SkeletonBox(height = 44.dp, cornerRadius = 8.dp)
                        }
                        // Export Options card skeleton
                        IAMSCard {
                            SkeletonBox(width = 120.dp, height = 22.dp)
                            Spacer(modifier = Modifier.height(spacing.lg))
                            SkeletonBox(height = 44.dp, cornerRadius = 8.dp)
                            Spacer(modifier = Modifier.height(spacing.md))
                            SkeletonBox(height = 44.dp, cornerRadius = 8.dp)
                        }
                    }
                }

                uiState.error != null && uiState.schedules.isEmpty() -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                text = uiState.error!!,
                                style = MaterialTheme.typography.bodyLarge,
                                color = MaterialTheme.colorScheme.error,
                                textAlign = TextAlign.Center
                            )
                            Spacer(modifier = Modifier.height(spacing.lg))
                            IAMSButton(
                                text = "Retry",
                                onClick = { viewModel.loadData() },
                                variant = IAMSButtonVariant.OUTLINE,
                                fullWidth = false
                            )
                        }
                    }
                }

                else -> {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .verticalScroll(rememberScrollState())
                            .padding(horizontal = spacing.screenPadding)
                            .padding(top = spacing.lg, bottom = spacing.xxxl),
                        verticalArrangement = Arrangement.spacedBy(spacing.lg)
                    ) {
                        // -- Generate Report card --
                        IAMSCard {
                            Text(
                                text = "Generate Report",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.SemiBold,
                                color = TextPrimary
                            )

                            Spacer(modifier = Modifier.height(spacing.lg))

                            // Class selector dropdown
                            ClassSelectorDropdown(
                                schedules = uiState.schedules,
                                selectedIndex = uiState.selectedScheduleIndex,
                                onSelect = { viewModel.selectSchedule(it) }
                            )

                            Spacer(modifier = Modifier.height(spacing.md))

                            // Report type toggle
                            ReportTypeSelector(
                                selected = uiState.reportType,
                                onSelect = { viewModel.setReportType(it) }
                            )

                            Spacer(modifier = Modifier.height(spacing.lg))

                            // Generate button
                            IAMSButton(
                                text = "Generate Report",
                                onClick = { viewModel.generateReport() },
                                enabled = uiState.selectedScheduleIndex >= 0 && !uiState.isGenerating,
                                isLoading = uiState.isGenerating,
                                size = IAMSButtonSize.LG
                            )
                        }

                        // -- Report Results card --
                        val report = uiState.generatedReport
                        if (report?.summary != null) {
                            IAMSCard {
                                // Header row with icon
                                Row(
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(
                                        Icons.Default.BarChart,
                                        contentDescription = "Report",
                                        modifier = Modifier.size(24.dp),
                                        tint = Primary
                                    )
                                    Spacer(modifier = Modifier.width(spacing.md))
                                    Text(
                                        text = "Report Results",
                                        style = MaterialTheme.typography.titleLarge,
                                        fontWeight = FontWeight.SemiBold,
                                        color = TextPrimary
                                    )
                                }

                                // Selected class name
                                val schedule = report.schedule
                                val className = if (schedule.subjectCode != null) {
                                    "${schedule.subjectCode} - ${schedule.subjectName}"
                                } else {
                                    schedule.subjectName
                                }
                                Spacer(modifier = Modifier.height(spacing.xs))
                                Text(
                                    text = className,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextSecondary
                                )

                                Spacer(modifier = Modifier.height(spacing.lg))

                                // Stats row
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceEvenly
                                ) {
                                    ReportStatItem(
                                        label = "Total",
                                        value = "${report.summary.totalClasses}",
                                        color = TextPrimary
                                    )
                                    ReportStatItem(
                                        label = "Present",
                                        value = "${report.summary.presentCount}",
                                        color = PresentFg
                                    )
                                    ReportStatItem(
                                        label = "Late",
                                        value = "${report.summary.lateCount}",
                                        color = LateFg
                                    )
                                    ReportStatItem(
                                        label = "Absent",
                                        value = "${report.summary.absentCount}",
                                        color = AbsentFg
                                    )
                                }

                                Spacer(modifier = Modifier.height(spacing.lg))
                                HorizontalDivider(color = Border, thickness = 1.dp)
                                Spacer(modifier = Modifier.height(spacing.lg))

                                // Attendance rate
                                val ratePercent = (report.summary.attendanceRate * 100).toInt()
                                val rateColor = when {
                                    ratePercent >= 80 -> PresentFg
                                    ratePercent >= 60 -> LateFg
                                    else -> AbsentFg
                                }

                                Column(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalAlignment = Alignment.CenterHorizontally
                                ) {
                                    Text(
                                        text = "Overall Attendance Rate",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = TextTertiary
                                    )
                                    Spacer(modifier = Modifier.height(spacing.xs))
                                    Text(
                                        text = "$ratePercent%",
                                        style = MaterialTheme.typography.headlineLarge,
                                        fontWeight = FontWeight.Bold,
                                        color = rateColor
                                    )
                                }

                                Spacer(modifier = Modifier.height(spacing.md))

                                // Attendance bar
                                AttendanceBar(report.summary)
                            }
                        }

                        // -- Export Options card --
                        IAMSCard {
                            Text(
                                text = "Export Options",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.SemiBold,
                                color = TextPrimary
                            )

                            Spacer(modifier = Modifier.height(spacing.lg))

                            IAMSButton(
                                text = "Export CSV",
                                onClick = {
                                    toastState.showToast("Coming soon", ToastType.INFO)
                                },
                                variant = IAMSButtonVariant.OUTLINE,
                                leadingIcon = {
                                    Icon(
                                        Icons.Default.Download,
                                        contentDescription = null,
                                        modifier = Modifier.size(20.dp),
                                        tint = Primary
                                    )
                                }
                            )

                            Spacer(modifier = Modifier.height(spacing.md))

                            IAMSButton(
                                text = "Export PDF",
                                onClick = {
                                    toastState.showToast("Coming soon", ToastType.INFO)
                                },
                                variant = IAMSButtonVariant.OUTLINE,
                                leadingIcon = {
                                    Icon(
                                        Icons.Default.Download,
                                        contentDescription = null,
                                        modifier = Modifier.size(20.dp),
                                        tint = Primary
                                    )
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ClassSelectorDropdown(
    schedules: List<ScheduleWithSummary>,
    selectedIndex: Int,
    onSelect: (Int) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }

    val selectedText = if (selectedIndex >= 0 && selectedIndex < schedules.size) {
        val s = schedules[selectedIndex].schedule
        if (s.subjectCode != null) "${s.subjectCode} - ${s.subjectName}" else s.subjectName
    } else {
        ""
    }

    Column {
        Text(
            text = "Select Class",
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Medium,
            color = TextPrimary
        )
        Spacer(modifier = Modifier.height(6.dp))

        ExposedDropdownMenuBox(
            expanded = expanded,
            onExpandedChange = { expanded = it }
        ) {
            OutlinedTextField(
                value = selectedText,
                onValueChange = {},
                readOnly = true,
                placeholder = {
                    Text(
                        text = if (schedules.isEmpty()) "No classes available" else "Choose a class",
                        color = TextTertiary
                    )
                },
                trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                modifier = Modifier
                    .menuAnchor(MenuAnchorType.PrimaryNotEditable)
                    .fillMaxWidth(),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Primary,
                    unfocusedBorderColor = Border,
                    focusedTextColor = TextPrimary,
                    unfocusedTextColor = TextPrimary,
                ),
                shape = IAMSThemeTokens.radius.mdShape,
                singleLine = true,
            )

            ExposedDropdownMenu(
                expanded = expanded,
                onDismissRequest = { expanded = false }
            ) {
                schedules.forEachIndexed { index, item ->
                    val label = if (item.schedule.subjectCode != null) {
                        "${item.schedule.subjectCode} - ${item.schedule.subjectName}"
                    } else {
                        item.schedule.subjectName
                    }
                    DropdownMenuItem(
                        text = {
                            Text(
                                text = label,
                                style = MaterialTheme.typography.bodyMedium,
                                color = TextPrimary
                            )
                        },
                        onClick = {
                            onSelect(index)
                            expanded = false
                        },
                        contentPadding = ExposedDropdownMenuDefaults.ItemContentPadding,
                    )
                }
            }
        }
    }
}

@Composable
private fun ReportTypeSelector(
    selected: String,
    onSelect: (String) -> Unit
) {
    val spacing = IAMSThemeTokens.spacing

    Column {
        Text(
            text = "Report Type",
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Medium,
            color = TextPrimary
        )
        Spacer(modifier = Modifier.height(6.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(spacing.sm)
        ) {
            IAMSButton(
                text = "Summary",
                onClick = { onSelect("summary") },
                variant = if (selected == "summary") IAMSButtonVariant.PRIMARY else IAMSButtonVariant.OUTLINE,
                modifier = Modifier.weight(1f),
                fullWidth = false,
                size = IAMSButtonSize.MD
            )
            IAMSButton(
                text = "Detailed",
                onClick = { onSelect("detailed") },
                variant = if (selected == "detailed") IAMSButtonVariant.PRIMARY else IAMSButtonVariant.OUTLINE,
                modifier = Modifier.weight(1f),
                fullWidth = false,
                size = IAMSButtonSize.MD
            )
        }
    }
}

@Composable
private fun AttendanceBar(summary: AttendanceSummaryResponse) {
    val total = summary.totalClasses.coerceAtLeast(1).toFloat()
    val presentFraction = summary.presentCount / total
    val lateFraction = summary.lateCount / total
    val absentFraction = summary.absentCount / total
    val earlyLeaveFraction = (1f - presentFraction - lateFraction - absentFraction).coerceAtLeast(0f)

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(12.dp)
            .clip(RoundedCornerShape(6.dp))
            .background(Secondary)
    ) {
        if (presentFraction > 0f) {
            Box(
                modifier = Modifier
                    .weight(presentFraction)
                    .height(12.dp)
                    .background(PresentFg)
            )
        }
        if (lateFraction > 0f) {
            Box(
                modifier = Modifier
                    .weight(lateFraction)
                    .height(12.dp)
                    .background(LateFg)
            )
        }
        if (earlyLeaveFraction > 0f) {
            Box(
                modifier = Modifier
                    .weight(earlyLeaveFraction)
                    .height(12.dp)
                    .background(EarlyLeaveFg)
            )
        }
        if (absentFraction > 0f) {
            Box(
                modifier = Modifier
                    .weight(absentFraction)
                    .height(12.dp)
                    .background(AbsentFg)
            )
        }
    }
}

@Composable
private fun ReportStatItem(
    label: String,
    value: String,
    color: Color
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = value,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = color
        )
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary
        )
    }
}

private fun dayOfWeekName(day: Int): String = when (day) {
    0 -> "Monday"
    1 -> "Tuesday"
    2 -> "Wednesday"
    3 -> "Thursday"
    4 -> "Friday"
    5 -> "Saturday"
    6 -> "Sunday"
    else -> ""
}
