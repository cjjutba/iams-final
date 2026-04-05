package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.NotificationService
import com.iams.app.data.model.ScheduleResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.LocalDate
import javax.inject.Inject

data class FacultyScheduleUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val allSchedules: List<ScheduleResponse> = emptyList(),
    val selectedDay: Int = jsDayToScheduleDay(LocalDate.now().dayOfWeek.value % 7),
)

/** Convert java.time DayOfWeek (1=Monday..7=Sunday) to schedule day (0=Monday..6=Sunday). */
private fun javaDayToScheduleDay(javaDow: Int): Int = javaDow - 1 // 1->0, 7->6

/** Convert JS-style day (0=Sunday) to schedule day (0=Monday). Used for default init only. */
private fun jsDayToScheduleDay(jsDay: Int): Int = if (jsDay == 0) 6 else jsDay - 1

@HiltViewModel
class FacultyScheduleViewModel @Inject constructor(
    private val apiService: ApiService,
    val notificationService: NotificationService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyScheduleUiState(
        selectedDay = javaDayToScheduleDay(LocalDate.now().dayOfWeek.value)
    ))
    val uiState: StateFlow<FacultyScheduleUiState> = _uiState.asStateFlow()

    init {
        loadSchedules()
    }

    fun loadSchedules() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = apiService.getMySchedules()
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        allSchedules = response.body() ?: emptyList(),
                        isLoading = false,
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Failed to load schedules",
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Failed to load schedules. Pull to refresh.",
                )
            }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
            try {
                val response = apiService.getMySchedules()
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        allSchedules = response.body() ?: emptyList(),
                    )
                }
            } catch (_: Exception) {}
            _uiState.value = _uiState.value.copy(isRefreshing = false)
        }
    }

    fun selectDay(day: Int) {
        _uiState.value = _uiState.value.copy(selectedDay = day)
    }

    /** Get today's schedule day index (0=Monday). */
    fun todayScheduleDay(): Int = javaDayToScheduleDay(LocalDate.now().dayOfWeek.value)

    /** Filter schedules for the selected day. */
    fun filteredSchedules(): List<ScheduleResponse> {
        val state = _uiState.value
        return state.allSchedules.filter { schedule ->
            schedule.dayOfWeekInt == state.selectedDay && schedule.isActive
        }
    }
}
