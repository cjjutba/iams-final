package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.BuildConfig
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.AttendanceWebSocketClient
import com.iams.app.data.api.NotificationService
import com.iams.app.data.api.TokenManager
import com.iams.app.data.model.LiveAttendanceResponse
import com.iams.app.data.model.ScheduleResponse
import com.iams.app.data.model.ScheduleConfigUpdateRequest
import com.iams.app.data.model.SessionStartRequest
import com.iams.app.data.model.StudentAttendanceStatus
import com.iams.app.data.model.UserResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import java.time.Duration
import java.time.LocalDate
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import java.util.Calendar
import javax.inject.Inject

enum class ScheduleTimeState { COMPLETED, ACTIVE, UPCOMING }

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
    val unreadNotificationCount: Int = 0,
    val liveAttendance: LiveAttendanceResponse? = null,
    val configSaving: Boolean = false,
)

@HiltViewModel
class FacultyHomeViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager,
    private val okHttpClient: OkHttpClient,
    val notificationService: NotificationService,
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyHomeUiState())
    val uiState: StateFlow<FacultyHomeUiState> = _uiState.asStateFlow()

    private var liveAttendanceJob: Job? = null
    private var wsClient: AttendanceWebSocketClient? = null
    private var wsObserverJob: Job? = null

    private val timeFormatter = DateTimeFormatter.ofPattern("HH:mm:ss")
    private val shortTimeFormatter = DateTimeFormatter.ofPattern("HH:mm")

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

                // Fetch unread notification count via centralized service
                val unreadCountJob = viewModelScope.launch {
                    try {
                        notificationService.fetchUnreadCount(apiService)
                    } catch (_: Exception) {}
                }

                userJob.join()
                schedulesJob.join()
                sessionsJob.join()
                unreadCountJob.join()

                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    initialLoadDone = true
                )

                // Auto-start polling if a current class has an active session
                val current = getCurrentClass()
                if (current != null && isSessionActive(current.id)) {
                    startLiveAttendancePolling(current.id)
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    initialLoadDone = true,
                    error = "Failed to load data. Pull to refresh."
                )
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
        loadData()
    }

    fun getGreeting(): String {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        return when {
            hour < 12 -> "Good morning"
            hour < 18 -> "Good afternoon"
            else -> "Good evening"
        }
    }

    private fun parseTime(timeStr: String): LocalTime? {
        return try {
            LocalTime.parse(timeStr, timeFormatter)
        } catch (_: Exception) {
            try {
                LocalTime.parse(timeStr, shortTimeFormatter)
            } catch (_: Exception) {
                null
            }
        }
    }

    fun getCurrentClass(): ScheduleResponse? {
        val now = LocalTime.now()
        return _uiState.value.todaySchedules.firstOrNull { schedule ->
            val start = parseTime(schedule.startTime) ?: return@firstOrNull false
            val end = parseTime(schedule.endTime) ?: return@firstOrNull false
            now in start..end
        }
    }

    fun getScheduleTimeState(schedule: ScheduleResponse): ScheduleTimeState {
        val now = LocalTime.now()
        val start = parseTime(schedule.startTime) ?: return ScheduleTimeState.UPCOMING
        val end = parseTime(schedule.endTime) ?: return ScheduleTimeState.UPCOMING
        return when {
            now.isAfter(end) -> ScheduleTimeState.COMPLETED
            now.isBefore(start) -> ScheduleTimeState.UPCOMING
            else -> ScheduleTimeState.ACTIVE
        }
    }

    fun getElapsedMinutes(schedule: ScheduleResponse): Long {
        val start = parseTime(schedule.startTime) ?: return 0
        return Duration.between(start, LocalTime.now()).toMinutes().coerceAtLeast(0)
    }

    fun getRemainingMinutes(schedule: ScheduleResponse): Long {
        val end = parseTime(schedule.endTime) ?: return 0
        return Duration.between(LocalTime.now(), end).toMinutes().coerceAtLeast(0)
    }

    fun getMinutesUntilStart(schedule: ScheduleResponse): Long {
        val start = parseTime(schedule.startTime) ?: return 0
        return Duration.between(LocalTime.now(), start).toMinutes().coerceAtLeast(0)
    }

    fun startLiveAttendancePolling(scheduleId: String) {
        liveAttendanceJob?.cancel()
        wsObserverJob?.cancel()

        // Create WebSocket client if needed
        if (wsClient == null) {
            wsClient = AttendanceWebSocketClient(
                "ws://${BuildConfig.BACKEND_HOST}:${BuildConfig.BACKEND_PORT}/api/v1/ws",
                okHttpClient,
                { tokenManager.accessToken }
            )
        }
        wsClient?.connect(scheduleId)

        // Observe attendance_summary from WebSocket for real-time updates
        wsObserverJob = viewModelScope.launch {
            wsClient?.attendanceSummary?.collect { msg ->
                if (msg != null) {
                    _uiState.value = _uiState.value.copy(
                        liveAttendance = LiveAttendanceResponse(
                            scheduleId = msg.scheduleId,
                            totalEnrolled = msg.totalEnrolled,
                            presentCount = msg.presentCount - (msg.late?.size ?: 0),
                            lateCount = msg.late?.size ?: 0,
                            absentCount = msg.totalEnrolled - msg.presentCount - (msg.earlyLeave?.size ?: 0),
                            earlyLeaveCount = msg.earlyLeave?.size ?: 0,
                            sessionActive = true,
                            present = msg.present?.map {
                                StudentAttendanceStatus(studentId = it.userId, studentName = it.name, status = "present")
                            },
                            absent = msg.absent?.map {
                                StudentAttendanceStatus(studentId = it.userId, studentName = it.name, status = "absent")
                            },
                            late = msg.late?.map {
                                StudentAttendanceStatus(studentId = it.userId, studentName = it.name, status = "late")
                            },
                            earlyLeave = msg.earlyLeave?.map {
                                StudentAttendanceStatus(studentId = it.userId, studentName = it.name, status = "early_leave")
                            }
                        )
                    )
                }
            }
        }

        // One initial REST fetch so the UI isn't empty while waiting for the first WS message
        liveAttendanceJob = viewModelScope.launch {
            try {
                val response = apiService.getLiveAttendance(scheduleId)
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(liveAttendance = response.body())
                }
            } catch (_: Exception) {}
        }
    }

    fun stopLiveAttendancePolling() {
        liveAttendanceJob?.cancel()
        liveAttendanceJob = null
        wsObserverJob?.cancel()
        wsObserverJob = null
        wsClient?.disconnect()
        _uiState.value = _uiState.value.copy(liveAttendance = null)
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
                    startLiveAttendancePolling(scheduleId)
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
                    stopLiveAttendancePolling()
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

    fun updateEarlyLeaveTimeout(scheduleId: String, minutes: Int) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(configSaving = true)
            try {
                val response = apiService.updateScheduleConfig(
                    scheduleId,
                    ScheduleConfigUpdateRequest(minutes)
                )
                if (response.isSuccessful) {
                    // Update the schedule in local state so the UI reflects the new value
                    val updatedSchedules = _uiState.value.todaySchedules.map {
                        if (it.id == scheduleId) response.body() ?: it else it
                    }
                    val updatedAll = _uiState.value.allSchedules.map {
                        if (it.id == scheduleId) response.body() ?: it else it
                    }
                    _uiState.value = _uiState.value.copy(
                        configSaving = false,
                        todaySchedules = updatedSchedules,
                        allSchedules = updatedAll,
                    )
                } else {
                    _uiState.value = _uiState.value.copy(configSaving = false)
                }
            } catch (_: Exception) {
                _uiState.value = _uiState.value.copy(configSaving = false)
            }
        }
    }

    fun clearSessionMessage() {
        _uiState.value = _uiState.value.copy(sessionMessage = null)
    }

    fun formatTime(timeStr: String): String {
        val time = parseTime(timeStr) ?: return timeStr
        return time.format(DateTimeFormatter.ofPattern("h:mm a"))
    }

    override fun onCleared() {
        super.onCleared()
        liveAttendanceJob?.cancel()
        wsObserverJob?.cancel()
        wsClient?.destroy()
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
