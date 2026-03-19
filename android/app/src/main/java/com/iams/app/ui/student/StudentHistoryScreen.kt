package com.iams.app.ui.student

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
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.data.model.AttendanceRecordResponse
import com.iams.app.ui.components.AttendanceStatus
import com.iams.app.ui.components.IAMSBadge
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

@Composable
fun StudentHistoryScreen(
    navController: NavController,
    viewModel: StudentHistoryViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    var showFilter by remember { mutableStateOf(false) }
    var startDate by remember { mutableStateOf("") }
    var endDate by remember { mutableStateOf("") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        IAMSHeader(
            title = "Attendance History",
            trailing = {
                IconButton(onClick = { showFilter = !showFilter }) {
                    Icon(
                        Icons.Default.CalendarMonth,
                        contentDescription = "Filter by date",
                        tint = Primary
                    )
                }
            }
        )

        // Date filter section
        if (showFilter) {
            DateFilterSection(
                startDate = startDate,
                endDate = endDate,
                onStartDateChange = { startDate = it },
                onEndDateChange = { endDate = it },
                onApply = {
                    viewModel.setDateFilter(
                        startDate = startDate.ifBlank { null },
                        endDate = endDate.ifBlank { null }
                    )
                },
                onClear = {
                    startDate = ""
                    endDate = ""
                    viewModel.clearFilter()
                }
            )
        }

        when {
            uiState.isLoading -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(color = Primary)
                }
            }

            uiState.error != null -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        modifier = Modifier.padding(horizontal = 16.dp)
                    ) {
                        Text(
                            text = uiState.error!!,
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.error,
                            textAlign = TextAlign.Center
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        IAMSButton(
                            text = "Retry",
                            onClick = { viewModel.loadHistory() },
                            variant = IAMSButtonVariant.OUTLINE,
                            size = IAMSButtonSize.SM,
                            fullWidth = false
                        )
                    }
                }
            }

            uiState.records.isEmpty() -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "No attendance records found",
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextSecondary
                    )
                }
            }

            else -> {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    item { Spacer(modifier = Modifier.height(4.dp)) }

                    items(uiState.records) { record ->
                        AttendanceRecordCard(record = record)
                    }

                    item { Spacer(modifier = Modifier.height(8.dp)) }
                }
            }
        }
    }
}

@Composable
private fun DateFilterSection(
    startDate: String,
    endDate: String,
    onStartDateChange: (String) -> Unit,
    onEndDateChange: (String) -> Unit,
    onApply: () -> Unit,
    onClear: () -> Unit,
) {
    IAMSCard(
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = "Filter by Date",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = Primary
            )

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedTextField(
                    value = startDate,
                    onValueChange = onStartDateChange,
                    label = { Text("Start", color = TextSecondary) },
                    placeholder = { Text("YYYY-MM-DD", color = TextTertiary) },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Primary,
                        unfocusedBorderColor = Border,
                        cursorColor = Primary
                    ),
                    trailingIcon = {
                        if (startDate.isNotBlank()) {
                            IconButton(onClick = { onStartDateChange("") }) {
                                Icon(
                                    Icons.Default.Clear,
                                    contentDescription = "Clear",
                                    modifier = Modifier.size(18.dp),
                                    tint = TextTertiary
                                )
                            }
                        }
                    }
                )

                OutlinedTextField(
                    value = endDate,
                    onValueChange = onEndDateChange,
                    label = { Text("End", color = TextSecondary) },
                    placeholder = { Text("YYYY-MM-DD", color = TextTertiary) },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Primary,
                        unfocusedBorderColor = Border,
                        cursorColor = Primary
                    ),
                    trailingIcon = {
                        if (endDate.isNotBlank()) {
                            IconButton(onClick = { onEndDateChange("") }) {
                                Icon(
                                    Icons.Default.Clear,
                                    contentDescription = "Clear",
                                    modifier = Modifier.size(18.dp),
                                    tint = TextTertiary
                                )
                            }
                        }
                    }
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End
            ) {
                IAMSButton(
                    text = "Clear",
                    onClick = onClear,
                    variant = IAMSButtonVariant.GHOST,
                    size = IAMSButtonSize.SM,
                    fullWidth = false
                )
                Spacer(modifier = Modifier.width(8.dp))
                IAMSButton(
                    text = "Apply",
                    onClick = onApply,
                    variant = IAMSButtonVariant.PRIMARY,
                    size = IAMSButtonSize.SM,
                    fullWidth = false
                )
            }
        }
    }
}

@Composable
private fun AttendanceRecordCard(record: AttendanceRecordResponse) {
    val status = when (record.status.lowercase()) {
        "present" -> AttendanceStatus.PRESENT
        "absent" -> AttendanceStatus.ABSENT
        "late" -> AttendanceStatus.LATE
        "early_leave" -> AttendanceStatus.EARLY_LEAVE
        else -> AttendanceStatus.ABSENT
    }

    IAMSCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Record details
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = record.studentName ?: "Class",
                    style = MaterialTheme.typography.titleMedium,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Medium,
                    color = Primary
                )

                Spacer(modifier = Modifier.height(2.dp))

                Text(
                    text = record.date,
                    style = MaterialTheme.typography.bodySmall,
                    fontSize = 12.sp,
                    color = TextSecondary
                )

                if (record.checkInTime != null) {
                    Text(
                        text = "Checked in: ${record.checkInTime}",
                        style = MaterialTheme.typography.bodySmall,
                        fontSize = 12.sp,
                        color = TextTertiary
                    )
                }
            }

            Spacer(modifier = Modifier.width(8.dp))

            // Status badge
            IAMSBadge(status = status)

            Spacer(modifier = Modifier.width(4.dp))

            Icon(
                Icons.AutoMirrored.Filled.KeyboardArrowRight,
                contentDescription = "Details",
                modifier = Modifier.size(20.dp),
                tint = TextTertiary
            )
        }
    }
}
