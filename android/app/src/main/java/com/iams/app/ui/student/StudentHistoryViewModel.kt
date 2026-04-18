package com.iams.app.ui.student

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.NotificationService
import com.iams.app.data.model.AttendanceRecordResponse
import com.iams.app.data.model.StudentAttendanceEvent
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.DateTimeFormatter
import java.util.Locale
import javax.inject.Inject

data class StudentHistoryUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val records: List<AttendanceRecordResponse> = emptyList(),
    val selectedMonth: YearMonth = YearMonth.now(),
    // "all" / "present" / "late" / "absent" / "early_leave".
    val selectedFilter: String = "all",
)

// Valid filter options for the status-pill row. Matches the backend
// enum `AttendanceStatus` values (lower-cased).
val STUDENT_HISTORY_FILTERS = listOf("all", "present", "late", "absent", "early_leave")

@HiltViewModel
class StudentHistoryViewModel @Inject constructor(
    private val apiService: ApiService,
    val notificationService: NotificationService,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    // Optional pre-filter by schedule (driven from Analytics subject drill-down).
    private val scheduleIdFilter: String? = savedStateHandle["scheduleId"]

    private val _uiState = MutableStateFlow(StudentHistoryUiState())
    val uiState: StateFlow<StudentHistoryUiState> = _uiState.asStateFlow()

    init {
        loadHistory()
        observeRealtimeEvents()
    }

    /**
     * Merge incoming live attendance events into the current month's list
     * instead of refetching. Only applies to events whose date falls in
     * the currently-displayed month — a CheckIn for today while the user
     * is browsing last month won't mutate anything they're looking at.
     */
    private fun observeRealtimeEvents() {
        viewModelScope.launch {
            notificationService.attendanceEvents.collect { event ->
                when (event) {
                    is StudentAttendanceEvent.CheckIn ->
                        applyEvent(event.attendanceId, event.scheduleId, event.status, event.checkInTime)
                    is StudentAttendanceEvent.EarlyLeave ->
                        applyEvent(event.attendanceId, event.scheduleId, "early_leave", null)
                    is StudentAttendanceEvent.EarlyLeaveReturn ->
                        applyEvent(event.attendanceId, event.scheduleId, event.restoredStatus, event.returnedAt)
                    is StudentAttendanceEvent.SnapshotUpdate -> {
                        // Reconcile any missed events during a reconnect
                        // gap by rerunning the month fetch silently.
                        if (_uiState.value.selectedMonth == YearMonth.now()) {
                            loadHistory(silent = true)
                        }
                    }
                }
            }
        }
    }

    private fun applyEvent(
        attendanceId: String,
        scheduleId: String,
        status: String,
        checkInTime: String?,
    ) {
        val state = _uiState.value
        val displayMonth = state.selectedMonth
        val today = LocalDate.now()
        // Only mutate if the event happened in the month the user is
        // currently viewing. Otherwise the refetch on re-navigation will
        // pick it up naturally.
        if (YearMonth.from(today) != displayMonth) return

        val existing = state.records.firstOrNull { it.id == attendanceId }
        val merged = if (existing != null) {
            existing.copy(
                status = status,
                checkInTime = checkInTime ?: existing.checkInTime,
            )
        } else {
            AttendanceRecordResponse(
                id = attendanceId,
                scheduleId = scheduleId,
                studentId = null,
                studentName = null,
                subjectCode = null,
                status = status,
                date = today.toString(),
                checkInTime = checkInTime,
                presenceScore = null,
                totalScans = null,
                scansPresent = null,
                remarks = null,
            )
        }

        val newRecords = if (existing != null) {
            state.records.map { if (it.id == attendanceId) merged else it }
        } else {
            (state.records + merged).sortedByDescending { it.date }
        }
        _uiState.value = state.copy(records = newRecords)
    }

    fun loadHistory(silent: Boolean = false) {
        viewModelScope.launch {
            if (!silent) {
                _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            }

            try {
                val month = _uiState.value.selectedMonth
                val startDate = month.atDay(1).format(DateTimeFormatter.ISO_LOCAL_DATE)
                val endDate = month.atEndOfMonth().format(DateTimeFormatter.ISO_LOCAL_DATE)

                val response = apiService.getMyAttendance(
                    startDate = startDate,
                    endDate = endDate
                )

                if (response.isSuccessful) {
                    val records = response.body() ?: emptyList()
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        records = records.sortedByDescending { it.date }
                    )
                } else if (!silent) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = "Failed to load attendance history"
                    )
                }
            } catch (e: Exception) {
                if (!silent) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = "Network error. Please check your connection."
                    )
                }
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
        loadHistory()
    }

    fun previousMonth() {
        val prev = _uiState.value.selectedMonth.minusMonths(1)
        _uiState.value = _uiState.value.copy(selectedMonth = prev)
        loadHistory()
    }

    fun nextMonth() {
        val next = _uiState.value.selectedMonth.plusMonths(1)
        // Don't navigate beyond current month
        if (!next.isAfter(YearMonth.now())) {
            _uiState.value = _uiState.value.copy(selectedMonth = next)
            loadHistory()
        }
    }

    fun setFilter(filter: String) {
        _uiState.value = _uiState.value.copy(selectedFilter = filter)
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    /**
     * Get filtered records based on selected status filter.
     */
    fun getFilteredRecords(): List<AttendanceRecordResponse> {
        val state = _uiState.value
        val statusFiltered = if (state.selectedFilter == "all") {
            state.records
        } else {
            state.records.filter { it.status.equals(state.selectedFilter, ignoreCase = true) }
        }
        // Apply the optional schedule pre-filter from the deep-link.
        return if (scheduleIdFilter.isNullOrBlank()) statusFiltered
        else statusFiltered.filter { it.scheduleId == scheduleIdFilter }
    }

    /** Returns the optional pre-filter schedule id so the UI can surface it. */
    fun getScheduleFilter(): String? = scheduleIdFilter

    /**
     * Format the selected month as "MMMM yyyy"
     */
    fun getFormattedMonth(): String {
        val formatter = DateTimeFormatter.ofPattern("MMMM yyyy", Locale.getDefault())
        return _uiState.value.selectedMonth.format(formatter)
    }
}
