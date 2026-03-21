package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.TokenManager
import com.iams.app.data.model.ScheduleResponse
import com.iams.app.data.model.SessionStartRequest
import com.iams.app.data.model.UserResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import java.util.Calendar
import javax.inject.Inject

data class FacultyHomeUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val initialLoadDone: Boolean = false,
    val error: String? = null,
    val user: UserResponse? = null,
    val todaySchedules: List<ScheduleResponse> = emptyList(),
    val allSchedules: List<ScheduleResponse> = emptyList(),
    val activeSessionIds: List<String> = emptyList(),
    val sessionLoading: Boolean = false,
    val sessionMessage: String? = null,
)

@HiltViewModel
class FacultyHomeViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyHomeUiState())
    val uiState: StateFlow<FacultyHomeUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    fun loadData() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                // Fetch user info
                val userJob = viewModelScope.launch {
                    try {
                        val response = apiService.getMe()
                        if (response.isSuccessful) {
                            _uiState.value = _uiState.value.copy(user = response.body())
                        }
                    } catch (_: Exception) {}
                }

                // Fetch schedules -- filter to today
                val schedulesJob = viewModelScope.launch {
                    try {
                        val response = apiService.getMySchedules()
                        if (response.isSuccessful) {
                            val allSchedules = response.body() ?: emptyList()
                            val todayDow = LocalDate.now().dayOfWeek.value - 1 // 0=Monday
                            val todaySchedules = allSchedules
                                .filter { it.dayOfWeekInt == todayDow }
                                .sortedBy { it.startTime }
                            _uiState.value = _uiState.value.copy(
                                todaySchedules = todaySchedules,
                                allSchedules = allSchedules
                            )
                        }
                    } catch (_: Exception) {}
                }

                // Fetch active sessions
                val sessionsJob = viewModelScope.launch {
                    try {
                        val response = apiService.getActiveSessions()
                        if (response.isSuccessful) {
                            val active = response.body()?.activeSessions ?: emptyList()
                            _uiState.value = _uiState.value.copy(activeSessionIds = active)
                        }
                    } catch (_: Exception) {}
                }

                userJob.join()
                schedulesJob.join()
                sessionsJob.join()

                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    initialLoadDone = true
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    initialLoadDone = true,
                    error = "Failed to load data. Pull to refresh."
                )
            }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
            loadData()
            _uiState.value = _uiState.value.copy(isRefreshing = false)
        }
    }

    fun getGreeting(): String {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        return when {
            hour < 12 -> "Good morning"
            hour < 18 -> "Good afternoon"
            else -> "Good evening"
        }
    }

    fun getCurrentClass(): ScheduleResponse? {
        val now = LocalTime.now()
        val timeFormatter = DateTimeFormatter.ofPattern("HH:mm:ss")
        val shortFormatter = DateTimeFormatter.ofPattern("HH:mm")

        return _uiState.value.todaySchedules.firstOrNull { schedule ->
            try {
                val startTime = try {
                    LocalTime.parse(schedule.startTime, timeFormatter)
                } catch (_: Exception) {
                    LocalTime.parse(schedule.startTime, shortFormatter)
                }
                val endTime = try {
                    LocalTime.parse(schedule.endTime, timeFormatter)
                } catch (_: Exception) {
                    LocalTime.parse(schedule.endTime, shortFormatter)
                }
                now in startTime..endTime
            } catch (_: Exception) {
                false
            }
        }
    }

    fun isSessionActive(scheduleId: String): Boolean {
        return _uiState.value.activeSessionIds.contains(scheduleId)
    }

    fun startSession(scheduleId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(sessionLoading = true, sessionMessage = null)
            try {
                val response = apiService.startSession(SessionStartRequest(scheduleId))
                if (response.isSuccessful) {
                    val result = response.body()
                    _uiState.value = _uiState.value.copy(
                        sessionLoading = false,
                        activeSessionIds = _uiState.value.activeSessionIds + scheduleId,
                        sessionMessage = "Session started with ${result?.studentCount ?: 0} students"
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        sessionLoading = false,
                        sessionMessage = "Failed to start session"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    sessionLoading = false,
                    sessionMessage = "Failed to start session"
                )
            }
        }
    }

    fun endSession(scheduleId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(sessionLoading = true, sessionMessage = null)
            try {
                val response = apiService.endSession(scheduleId)
                if (response.isSuccessful) {
                    val result = response.body()
                    _uiState.value = _uiState.value.copy(
                        sessionLoading = false,
                        activeSessionIds = _uiState.value.activeSessionIds.filter { it != scheduleId },
                        sessionMessage = "Session ended. ${result?.presentCount ?: 0}/${result?.totalStudents ?: 0} present."
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        sessionLoading = false,
                        sessionMessage = "Failed to end session"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    sessionLoading = false,
                    sessionMessage = "Failed to end session"
                )
            }
        }
    }

    fun clearSessionMessage() {
        _uiState.value = _uiState.value.copy(sessionMessage = null)
    }

    fun formatTime(timeStr: String): String {
        return try {
            val formatter = DateTimeFormatter.ofPattern("HH:mm:ss")
            val shortFormatter = DateTimeFormatter.ofPattern("HH:mm")
            val time = try {
                LocalTime.parse(timeStr, formatter)
            } catch (_: Exception) {
                LocalTime.parse(timeStr, shortFormatter)
            }
            time.format(DateTimeFormatter.ofPattern("h:mm a"))
        } catch (_: Exception) {
            timeStr
        }
    }

    fun logout() {
        viewModelScope.launch {
            try {
                apiService.logout()
            } catch (_: Exception) {}
            tokenManager.clearTokens()
        }
    }
}
