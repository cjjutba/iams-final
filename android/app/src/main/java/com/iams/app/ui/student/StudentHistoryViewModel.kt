package com.iams.app.ui.student

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.AttendanceRecordResponse
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
    val selectedFilter: String = "all", // "all", "present", "late", "absent"
)

@HiltViewModel
class StudentHistoryViewModel @Inject constructor(
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(StudentHistoryUiState())
    val uiState: StateFlow<StudentHistoryUiState> = _uiState.asStateFlow()

    init {
        loadHistory()
    }

    fun loadHistory() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

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
                        records = records.sortedByDescending { it.date }
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Failed to load attendance history"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Network error. Please check your connection."
                )
            }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
            loadHistory()
            _uiState.value = _uiState.value.copy(isRefreshing = false)
        }
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
        return if (state.selectedFilter == "all") {
            state.records
        } else {
            state.records.filter { it.status.equals(state.selectedFilter, ignoreCase = true) }
        }
    }

    /**
     * Format the selected month as "MMMM yyyy"
     */
    fun getFormattedMonth(): String {
        val formatter = DateTimeFormatter.ofPattern("MMMM yyyy", Locale.getDefault())
        return _uiState.value.selectedMonth.format(formatter)
    }
}
