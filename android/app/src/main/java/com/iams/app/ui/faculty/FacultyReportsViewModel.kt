package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.AttendanceSummaryResponse
import com.iams.app.data.model.ScheduleResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ScheduleWithSummary(
    val schedule: ScheduleResponse,
    val summary: AttendanceSummaryResponse? = null,
    val isLoadingSummary: Boolean = false,
)

data class FacultyReportsUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val schedules: List<ScheduleWithSummary> = emptyList(),
    val selectedScheduleIndex: Int = -1,
    val reportType: String = "summary",
    val generatedReport: ScheduleWithSummary? = null,
    val isGenerating: Boolean = false,
)

@HiltViewModel
class FacultyReportsViewModel @Inject constructor(
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyReportsUiState())
    val uiState: StateFlow<FacultyReportsUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    fun loadData() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                val response = apiService.getMySchedules()
                if (response.isSuccessful) {
                    val schedules = response.body() ?: emptyList()
                    val schedulesWithSummary = schedules.map { schedule ->
                        ScheduleWithSummary(schedule = schedule)
                    }
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        schedules = schedulesWithSummary
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = "Failed to load schedules"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = "Network error. Please check your connection."
                )
            }
        }
    }

    fun selectSchedule(index: Int) {
        _uiState.value = _uiState.value.copy(
            selectedScheduleIndex = index,
            generatedReport = null
        )
    }

    fun setReportType(type: String) {
        _uiState.value = _uiState.value.copy(reportType = type)
    }

    fun generateReport() {
        val state = _uiState.value
        val index = state.selectedScheduleIndex
        if (index < 0 || index >= state.schedules.size) return

        val selected = state.schedules[index]
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isGenerating = true, generatedReport = null)

            try {
                val response = apiService.getScheduleAttendanceSummary(selected.schedule.id)
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isGenerating = false,
                        generatedReport = selected.copy(
                            summary = response.body(),
                            isLoadingSummary = false
                        )
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isGenerating = false,
                        error = "Failed to generate report"
                    )
                }
            } catch (_: Exception) {
                _uiState.value = _uiState.value.copy(
                    isGenerating = false,
                    error = "Network error generating report"
                )
            }
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        loadData()
    }
}
