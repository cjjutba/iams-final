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
                val response = apiService.getSchedules()
                if (response.isSuccessful) {
                    val schedules = response.body() ?: emptyList()
                    val schedulesWithSummary = schedules.map { schedule ->
                        ScheduleWithSummary(
                            schedule = schedule,
                            isLoadingSummary = true
                        )
                    }
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        schedules = schedulesWithSummary
                    )

                    // Load attendance summary for each schedule
                    schedulesWithSummary.forEachIndexed { index, item ->
                        loadSummaryForSchedule(index, item.schedule.id)
                    }
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Failed to load schedules"
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

    private fun loadSummaryForSchedule(index: Int, scheduleId: String) {
        viewModelScope.launch {
            try {
                val response = apiService.getScheduleAttendanceSummary(scheduleId)
                if (response.isSuccessful) {
                    val current = _uiState.value.schedules.toMutableList()
                    if (index < current.size) {
                        current[index] = current[index].copy(
                            summary = response.body(),
                            isLoadingSummary = false
                        )
                        _uiState.value = _uiState.value.copy(schedules = current)
                    }
                } else {
                    val current = _uiState.value.schedules.toMutableList()
                    if (index < current.size) {
                        current[index] = current[index].copy(isLoadingSummary = false)
                        _uiState.value = _uiState.value.copy(schedules = current)
                    }
                }
            } catch (_: Exception) {
                val current = _uiState.value.schedules.toMutableList()
                if (index < current.size) {
                    current[index] = current[index].copy(isLoadingSummary = false)
                    _uiState.value = _uiState.value.copy(schedules = current)
                }
            }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRefreshing = true)
            loadData()
            _uiState.value = _uiState.value.copy(isRefreshing = false)
        }
    }
}
