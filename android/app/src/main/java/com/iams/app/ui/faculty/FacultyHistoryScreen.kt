package com.iams.app.ui.faculty

import androidx.compose.animation.AnimatedVisibility
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
import androidx.compose.material.icons.filled.CalendarToday
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.IconButton
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.TabRowDefaults
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.AttendanceRecordResponse
import com.iams.app.ui.components.CardSkeleton
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.NotificationBellButton
import com.iams.app.ui.components.ToastType
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.EarlyLeaveFg
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.PrimaryForeground
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FacultyHistoryScreen(
    navController: NavController,
    viewModel: FacultyHistoryViewModel = hiltViewModel(),
    alertsViewModel: FacultyAlertsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing
    val toastState = LocalToastState.current
    var selectedTabIndex by rememberSaveable { mutableIntStateOf(0) }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            toastState.showToast(it, ToastType.ERROR)
            viewModel.clearError()
        }
    }

    LaunchedEffect(uiState.exportSuccess) {
        uiState.exportSuccess?.let {
            toastState.showToast(it, ToastType.SUCCESS)
            viewModel.clearExportSuccess()
        }
    }

    val context = LocalContext.current

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        IAMSHeader(
            title = "History",
            trailing = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (uiState.hasLoaded && uiState.sessions.isNotEmpty()) {
                        IconButton(
                            onClick = { viewModel.exportPdf(context) },
                            enabled = !uiState.isExporting,
                        ) {
                            if (uiState.isExporting) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(20.dp),
                                    strokeWidth = 2.dp,
                                    color = Primary,
                                )
                            } else {
                                Icon(
                                    Icons.Default.Download,
                                    contentDescription = "Export PDF",
                                    tint = Primary,
                                )
                            }
                        }
                    }
                    NotificationBellButton(
                        notificationService = viewModel.notificationService,
                        onClick = { navController.navigate(Routes.FACULTY_NOTIFICATIONS) },
                    )
                }
            },
        )

        // Tab Row
        TabRow(
            selectedTabIndex = selectedTabIndex,
            containerColor = Background,
            contentColor = Primary,
            indicator = { tabPositions ->
                if (selectedTabIndex < tabPositions.size) {
                    TabRowDefaults.SecondaryIndicator(
                        modifier = Modifier.tabIndicatorOffset(tabPositions[selectedTabIndex]),
                        color = Primary,
                    )
                }
            },
        ) {
            Tab(
                selected = selectedTabIndex == 0,
                onClick = { selectedTabIndex = 0 },
                text = {
                    Text(
                        text = "Attendance",
                        fontWeight = if (selectedTabIndex == 0) FontWeight.SemiBold else FontWeight.Normal,
                        color = if (selectedTabIndex == 0) Primary else TextSecondary,
                    )
                },
            )
            Tab(
                selected = selectedTabIndex == 1,
                onClick = { selectedTabIndex = 1 },
                text = {
                    Text(
                        text = "Alerts",
                        fontWeight = if (selectedTabIndex == 1) FontWeight.SemiBold else FontWeight.Normal,
                        color = if (selectedTabIndex == 1) Primary else TextSecondary,
                    )
                },
            )
        }

        when (selectedTabIndex) {
            0 -> AttendanceHistoryTab(viewModel = viewModel)
            1 -> FacultyAlertsContent(navController = navController, viewModel = alertsViewModel)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AttendanceHistoryTab(
    viewModel: FacultyHistoryViewModel,
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing

    var classPickerExpanded by remember { mutableStateOf(false) }
    var showStartDatePicker by remember { mutableStateOf(false) }
    var showEndDatePicker by remember { mutableStateOf(false) }

    val displayDateFormatter = DateTimeFormatter.ofPattern("MMM d, yyyy")

    // Date pickers
    if (showStartDatePicker) {
        val datePickerState = rememberDatePickerState(
            initialSelectedDateMillis = uiState.startDate
                .atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli()
        )
        DatePickerDialog(
            onDismissRequest = { showStartDatePicker = false },
            confirmButton = {
                TextButton(onClick = {
                    datePickerState.selectedDateMillis?.let { millis ->
                        val date = Instant.ofEpochMilli(millis)
                            .atZone(ZoneId.systemDefault()).toLocalDate()
                        viewModel.setStartDate(date)
                    }
                    showStartDatePicker = false
                }) {
                    Text("OK", color = Primary)
                }
            },
            dismissButton = {
                TextButton(onClick = { showStartDatePicker = false }) {
                    Text("Cancel", color = TextSecondary)
                }
            },
        ) {
            DatePicker(state = datePickerState)
        }
    }

    if (showEndDatePicker) {
        val datePickerState = rememberDatePickerState(
            initialSelectedDateMillis = uiState.endDate
                .atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli()
        )
        DatePickerDialog(
            onDismissRequest = { showEndDatePicker = false },
            confirmButton = {
                TextButton(onClick = {
                    datePickerState.selectedDateMillis?.let { millis ->
                        val date = Instant.ofEpochMilli(millis)
                            .atZone(ZoneId.systemDefault()).toLocalDate()
                        viewModel.setEndDate(date)
                    }
                    showEndDatePicker = false
                }) {
                    Text("OK", color = Primary)
                }
            },
            dismissButton = {
                TextButton(onClick = { showEndDatePicker = false }) {
                    Text("Cancel", color = TextSecondary)
                }
            },
        ) {
            DatePicker(state = datePickerState)
        }
    }

    // Loading state
    if (uiState.isLoading && !uiState.hasLoaded) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(spacing.lg),
            verticalArrangement = Arrangement.spacedBy(spacing.sm),
        ) {
            repeat(3) { CardSkeleton() }
        }
        return
    }

    LazyColumn(
        contentPadding = PaddingValues(
            start = spacing.screenPadding,
            end = spacing.screenPadding,
            top = spacing.lg,
            bottom = spacing.xxxl,
        ),
        verticalArrangement = Arrangement.spacedBy(spacing.md),
        modifier = Modifier.fillMaxSize(),
    ) {
        // Class selector card
        item {
            IAMSCard {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { classPickerExpanded = !classPickerExpanded },
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        Icons.Default.FilterList,
                        contentDescription = null,
                        modifier = Modifier.size(20.dp),
                        tint = Primary,
                    )
                    Spacer(modifier = Modifier.width(spacing.sm))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "Select Classes",
                            style = MaterialTheme.typography.bodyLarge,
                            fontWeight = FontWeight.SemiBold,
                            color = TextPrimary,
                        )
                        Text(
                            text = "${uiState.selectedScheduleIds.size} of ${uiState.schedules.size} selected",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary,
                        )
                    }
                    Icon(
                        if (classPickerExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                        contentDescription = null,
                        tint = TextSecondary,
                    )
                }

                AnimatedVisibility(visible = classPickerExpanded) {
                    Column {
                        Spacer(modifier = Modifier.height(spacing.sm))
                        HorizontalDivider(color = Border, thickness = 1.dp)
                        Spacer(modifier = Modifier.height(spacing.xs))

                        // Select All
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { viewModel.toggleSelectAll() }
                                .padding(vertical = spacing.xs),
                        ) {
                            Checkbox(
                                checked = uiState.selectAll,
                                onCheckedChange = { viewModel.toggleSelectAll() },
                                colors = CheckboxDefaults.colors(
                                    checkedColor = Primary,
                                    checkmarkColor = PrimaryForeground,
                                ),
                            )
                            Spacer(modifier = Modifier.width(spacing.sm))
                            Text(
                                text = "All Classes",
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.SemiBold,
                                color = TextPrimary,
                            )
                        }

                        uiState.schedules.forEach { schedule ->
                            val label = if (schedule.subjectCode != null) {
                                "${schedule.subjectCode} - ${schedule.subjectName}"
                            } else {
                                schedule.subjectName
                            }
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { viewModel.toggleScheduleSelection(schedule.id) }
                                    .padding(vertical = spacing.xs),
                            ) {
                                Checkbox(
                                    checked = uiState.selectedScheduleIds.contains(schedule.id),
                                    onCheckedChange = { viewModel.toggleScheduleSelection(schedule.id) },
                                    colors = CheckboxDefaults.colors(
                                        checkedColor = Primary,
                                        checkmarkColor = PrimaryForeground,
                                    ),
                                )
                                Spacer(modifier = Modifier.width(spacing.sm))
                                Text(
                                    text = label,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = TextPrimary,
                                )
                            }
                        }
                    }
                }
            }
        }

        // Date range pickers
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(spacing.sm),
            ) {
                // Start date
                IAMSCard(
                    modifier = Modifier.weight(1f),
                    onClick = { showStartDatePicker = true },
                ) {
                    Text(
                        text = "From",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextTertiary,
                    )
                    Spacer(modifier = Modifier.height(spacing.xs))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            Icons.Default.CalendarToday,
                            contentDescription = null,
                            modifier = Modifier.size(16.dp),
                            tint = Primary,
                        )
                        Spacer(modifier = Modifier.width(spacing.sm))
                        Text(
                            text = uiState.startDate.format(displayDateFormatter),
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Medium,
                            color = TextPrimary,
                        )
                    }
                }

                // End date
                IAMSCard(
                    modifier = Modifier.weight(1f),
                    onClick = { showEndDatePicker = true },
                ) {
                    Text(
                        text = "To",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextTertiary,
                    )
                    Spacer(modifier = Modifier.height(spacing.xs))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            Icons.Default.CalendarToday,
                            contentDescription = null,
                            modifier = Modifier.size(16.dp),
                            tint = Primary,
                        )
                        Spacer(modifier = Modifier.width(spacing.sm))
                        Text(
                            text = uiState.endDate.format(displayDateFormatter),
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Medium,
                            color = TextPrimary,
                        )
                    }
                }
            }
        }

        // Apply Filters button
        item {
            IAMSButton(
                text = "Apply Filters",
                onClick = { viewModel.loadHistory() },
                enabled = uiState.selectedScheduleIds.isNotEmpty() && !uiState.isLoading,
                isLoading = uiState.isLoading && uiState.hasLoaded,
                size = IAMSButtonSize.LG,
            )
        }

        // Summary card
        if (uiState.hasLoaded) {
            item {
                val summary = uiState.overallSummary
                IAMSCard {
                    Text(
                        text = "Summary",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = TextPrimary,
                    )
                    Spacer(modifier = Modifier.height(spacing.md))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceEvenly,
                    ) {
                        SummaryStatItem("Sessions", "${summary.totalSessions}", TextPrimary)
                        SummaryStatItem("Present", "${summary.totalPresent}", PresentFg)
                        SummaryStatItem("Late", "${summary.totalLate}", LateFg)
                        SummaryStatItem("Absent", "${summary.totalAbsent}", AbsentFg)
                    }

                    Spacer(modifier = Modifier.height(spacing.md))
                    HorizontalDivider(color = Border, thickness = 1.dp)
                    Spacer(modifier = Modifier.height(spacing.md))

                    val ratePercent = (summary.attendanceRate * 100).toInt()
                    val rateColor = when {
                        ratePercent >= 80 -> PresentFg
                        ratePercent >= 60 -> LateFg
                        else -> AbsentFg
                    }
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
                            text = "$ratePercent%",
                            style = MaterialTheme.typography.headlineMedium,
                            fontWeight = FontWeight.Bold,
                            color = rateColor,
                        )
                    }
                }
            }
        }

        // Session cards
        if (uiState.hasLoaded) {
            if (uiState.sessions.isEmpty()) {
                item {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 48.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(
                            text = "No attendance records found",
                            style = MaterialTheme.typography.bodyLarge,
                            color = TextSecondary,
                            textAlign = TextAlign.Center,
                        )
                        Spacer(modifier = Modifier.height(spacing.sm))
                        Text(
                            text = "Try adjusting the date range or class selection",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextTertiary,
                            textAlign = TextAlign.Center,
                        )
                    }
                }
            } else {
                item {
                    Text(
                        text = "Sessions",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = TextPrimary,
                    )
                }
                items(uiState.sessions, key = { "${it.date}|${it.scheduleId}" }) { session ->
                    SessionCard(session = session)
                }
            }
        }

    }
}

@Composable
private fun SummaryStatItem(
    label: String,
    value: String,
    color: androidx.compose.ui.graphics.Color,
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = value,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = color,
        )
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary,
        )
    }
}

@Composable
private fun SessionCard(session: SessionSummary) {
    var expanded by remember { mutableStateOf(false) }
    val spacing = IAMSThemeTokens.spacing
    val displayDateFormatter = DateTimeFormatter.ofPattern("MMM d, yyyy")

    IAMSCard(onClick = { expanded = !expanded }) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = if (session.subjectCode != null) {
                        "${session.subjectCode} - ${session.subjectName}"
                    } else {
                        session.subjectName
                    },
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = TextPrimary,
                )
                Spacer(modifier = Modifier.height(spacing.xs))
                Text(
                    text = try {
                        LocalDate.parse(session.date).format(displayDateFormatter)
                    } catch (_: Exception) {
                        session.date
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary,
                )
            }
            Icon(
                if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                contentDescription = null,
                tint = TextSecondary,
            )
        }

        Spacer(modifier = Modifier.height(spacing.sm))

        // Status counts row
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(spacing.md),
        ) {
            StatusChip("P: ${session.presentCount}", PresentFg)
            StatusChip("L: ${session.lateCount}", LateFg)
            StatusChip("A: ${session.absentCount}", AbsentFg)
            if (session.earlyLeaveCount > 0) {
                StatusChip("EL: ${session.earlyLeaveCount}", EarlyLeaveFg)
            }
        }

        // Expanded student-by-student list
        AnimatedVisibility(visible = expanded) {
            Column {
                Spacer(modifier = Modifier.height(spacing.sm))
                HorizontalDivider(color = Border, thickness = 1.dp)
                Spacer(modifier = Modifier.height(spacing.sm))

                if (session.records.isEmpty()) {
                    Text(
                        text = "No student records",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextTertiary,
                    )
                } else {
                    session.records.forEach { record ->
                        StudentRecordRow(record = record)
                        Spacer(modifier = Modifier.height(spacing.xs))
                    }
                }
            }
        }
    }
}

@Composable
private fun StatusChip(
    text: String,
    color: androidx.compose.ui.graphics.Color,
) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(4.dp))
            .background(color.copy(alpha = 0.1f))
            .padding(horizontal = 8.dp, vertical = 2.dp),
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.SemiBold,
            color = color,
        )
    }
}

@Composable
private fun StudentRecordRow(record: AttendanceRecordResponse) {
    val spacing = IAMSThemeTokens.spacing
    val statusColor = when (record.status.lowercase()) {
        "present" -> PresentFg
        "late" -> LateFg
        "absent" -> AbsentFg
        "early_leave" -> EarlyLeaveFg
        else -> TextSecondary
    }
    val statusLabel = when (record.status.lowercase()) {
        "present" -> "Present"
        "late" -> "Late"
        "absent" -> "Absent"
        "early_leave" -> "Early Leave"
        else -> record.status
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = record.studentName ?: "Unknown",
            style = MaterialTheme.typography.bodySmall,
            color = TextPrimary,
            modifier = Modifier.weight(1f),
        )
        Box(
            modifier = Modifier
                .clip(RoundedCornerShape(4.dp))
                .background(statusColor.copy(alpha = 0.1f))
                .padding(horizontal = 8.dp, vertical = 2.dp),
        ) {
            Text(
                text = statusLabel,
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Medium,
                color = statusColor,
            )
        }
    }
}
