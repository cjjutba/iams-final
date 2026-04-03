package com.iams.app.ui.student

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.model.ScheduleResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.LocalDate
import javax.inject.Inject

data class StudentScheduleUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val allSchedules: List<ScheduleResponse> = emptyList(),
    val selectedDay: Int = todayBackendDay(), // 0=Monday, 6=Sunday
)

/**
 * Convert current system day to backend format (0=Monday, 6=Sunday).
 */
private fun todayBackendDay(): Int {
    // Java DayOfWeek: MONDAY=1 ... SUNDAY=7
    return LocalDate.now().dayOfWeek.value - 1
}

@HiltViewModel
class StudentScheduleViewModel @Inject constructor(
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(StudentScheduleUiState())
    val uiState: StateFlow<StudentScheduleUiState> = _uiState.asStateFlow()

    init {
        loadSchedules()
    }

    fun loadSchedules() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                val response = apiService.getMySchedules()

                if (response.isSuccessful) {
                    val schedules = response.body() ?: emptyList()
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        allSchedules = schedules
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

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
        loadSchedules()
    }

    fun selectDay(day: Int) {
        _uiState.value = _uiState.value.copy(selectedDay = day)
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    /**
     * Get schedules for the currently selected day, sorted by start time.
     */
    fun getSelectedDaySchedules(): List<ScheduleResponse> {
        val state = _uiState.value
        return state.allSchedules
            .filter { it.dayOfWeekInt == state.selectedDay }
            .sortedBy { it.startTime }
    }
}
