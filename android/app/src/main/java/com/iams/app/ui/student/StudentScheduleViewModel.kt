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
import javax.inject.Inject

data class StudentScheduleUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val schedulesByDay: Map<String, List<ScheduleResponse>> = emptyMap(),
)

@HiltViewModel
class StudentScheduleViewModel @Inject constructor(
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(StudentScheduleUiState())
    val uiState: StateFlow<StudentScheduleUiState> = _uiState.asStateFlow()

    private val dayOrder = listOf(
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
    )

    init {
        loadSchedules()
    }

    fun loadSchedules() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                val response = apiService.getSchedules()

                if (response.isSuccessful) {
                    val schedules = response.body() ?: emptyList()
                    val grouped = schedules.groupBy { it.dayOfWeek }
                    // Sort by day order
                    val sorted = linkedMapOf<String, List<ScheduleResponse>>()
                    for (day in dayOrder) {
                        val daySchedules = grouped[day]
                        if (daySchedules != null) {
                            sorted[day] = daySchedules.sortedBy { it.startTime }
                        }
                    }
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        schedulesByDay = sorted
                    )
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
}
