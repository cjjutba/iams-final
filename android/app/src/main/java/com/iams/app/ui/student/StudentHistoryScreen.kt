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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
import com.iams.app.ui.components.AttendanceStatus
import com.iams.app.ui.components.IAMSBadge
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSButtonVariant
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.PrimaryForeground
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

private data class FilterOption(
    val label: String,
    val value: String, // "all", "present", "late", "absent"
)

private val FILTERS = listOf(
    FilterOption("All", "all"),
    FilterOption("Present", "present"),
    FilterOption("Late", "late"),
    FilterOption("Absent", "absent"),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudentHistoryScreen(
    navController: NavController,
    viewModel: StudentHistoryViewModel = hiltViewModel()
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

    // Error state (no cached data)
    if (uiState.error != null && uiState.records.isEmpty() && !uiState.isLoading) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(Background)
        ) {
            IAMSHeader(title = "History")

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
                        text = "Unable to load attendance history. Please try again.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextSecondary,
                        textAlign = TextAlign.Center
                    )
                    Spacer(modifier = Modifier.height(spacing.lg))
                    IAMSButton(
                        text = "Retry",
                        onClick = {
                            viewModel.clearError()
                            viewModel.loadHistory()
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

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        IAMSHeader(title = "History")

        // Filters container
        Column(
            modifier = Modifier.fillMaxWidth()
        ) {
            // Month selector row
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(
                        horizontal = spacing.lg,
                        vertical = spacing.lg
                    ),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                IconButton(
                    onClick = { viewModel.previousMonth() },
                    modifier = Modifier.size(36.dp)
                ) {
                    Icon(
                        Icons.AutoMirrored.Filled.KeyboardArrowLeft,
                        contentDescription = "Previous month",
                        modifier = Modifier.size(20.dp),
                        tint = Primary
                    )
                }

                Text(
                    text = viewModel.getFormattedMonth(),
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = Primary,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.weight(1f)
                )

                IconButton(
                    onClick = { viewModel.nextMonth() },
                    modifier = Modifier.size(36.dp)
                ) {
                    Icon(
                        Icons.AutoMirrored.Filled.KeyboardArrowRight,
                        contentDescription = "Next month",
                        modifier = Modifier.size(20.dp),
                        tint = Primary
                    )
                }
            }

            // Status filter pills
            LazyRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = spacing.lg),
                horizontalArrangement = Arrangement.spacedBy(spacing.sm)
            ) {
                items(FILTERS) { filter ->
                    FilterPill(
                        label = filter.label,
                        isSelected = filter.value == uiState.selectedFilter,
                        onClick = { viewModel.setFilter(filter.value) }
                    )
                }
            }

            Spacer(modifier = Modifier.height(spacing.lg))
            HorizontalDivider(thickness = 1.dp, color = Border)
        }

        // Records list
        val filteredRecords = viewModel.getFilteredRecords()

        PullToRefreshBox(
            isRefreshing = uiState.isRefreshing,
            onRefresh = { viewModel.refresh() },
            modifier = Modifier.fillMaxSize()
        ) {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = spacing.lg),
            ) {
                item { Spacer(modifier = Modifier.height(spacing.lg)) }

                if (filteredRecords.isNotEmpty()) {
                    items(filteredRecords, key = { it.id }) { record ->
                        HistoryRecordCard(record = record)
                        Spacer(modifier = Modifier.height(spacing.md))
                    }
                } else if (!uiState.isLoading) {
                    item {
                        HistoryEmptyState(formattedMonth = viewModel.getFormattedMonth())
                    }
                }

                item { Spacer(modifier = Modifier.height(spacing.lg)) }
            }
        }
    }
}

@Composable
private fun FilterPill(
    label: String,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    val bgColor = if (isSelected) Primary else Secondary
    val textColor = if (isSelected) PrimaryForeground else TextSecondary

    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(9999.dp))
            .background(bgColor)
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 8.dp)
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
            color = textColor
        )
    }
}

@Composable
private fun HistoryRecordCard(record: AttendanceRecordResponse) {
    val spacing = IAMSThemeTokens.spacing
    val status = parseAttendanceStatus(record.status)

    IAMSCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            // Date
            Text(
                text = formatDateForHistory(record.date),
                style = MaterialTheme.typography.bodySmall,
                color = TextTertiary
            )

            Spacer(modifier = Modifier.height(spacing.xs))

            // Check-in time
            if (!record.checkInTime.isNullOrBlank()) {
                Text(
                    text = "Check-in: ${formatTimeForDisplay(record.checkInTime)}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary
                )
                Spacer(modifier = Modifier.height(spacing.sm))
            }

            // Status badge + presence score
            Row(
                verticalAlignment = Alignment.CenterVertically
            ) {
                IAMSBadge(status = status)

                if (record.presenceScore != null) {
                    Spacer(modifier = Modifier.width(spacing.sm))
                    Text(
                        text = "${String.format("%.1f", record.presenceScore)}% present",
                        style = MaterialTheme.typography.bodyMedium,
                        color = TextSecondary
                    )
                }
            }
        }
    }
}

@Composable
private fun HistoryEmptyState(formattedMonth: String) {
    val spacing = IAMSThemeTokens.spacing

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "No attendance records yet",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(spacing.sm))
        Text(
            text = "No records found for $formattedMonth",
            style = MaterialTheme.typography.bodyMedium,
            color = TextTertiary,
            textAlign = TextAlign.Center
        )
    }
}

// ── Utility functions ──

private fun parseAttendanceStatus(status: String): AttendanceStatus {
    return when (status.lowercase()) {
        "present" -> AttendanceStatus.PRESENT
        "late" -> AttendanceStatus.LATE
        "absent" -> AttendanceStatus.ABSENT
        "early_leave" -> AttendanceStatus.EARLY_LEAVE
        else -> AttendanceStatus.ABSENT
    }
}

/**
 * Format "YYYY-MM-DD" to "EEEE, MMM d" (e.g., "Monday, Mar 15")
 */
private fun formatDateForHistory(date: String): String {
    return try {
        val localDate = LocalDate.parse(date)
        localDate.format(DateTimeFormatter.ofPattern("EEEE, MMM d", Locale.getDefault()))
    } catch (_: Exception) {
        date
    }
}

/**
 * Format "HH:MM:SS" or "HH:MM" to "h:mm AM/PM"
 */
private fun formatTimeForDisplay(time: String): String {
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
