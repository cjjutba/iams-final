package com.iams.app.ui.student

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.TokenManager
import com.iams.app.data.model.AttendanceRecordResponse
import com.iams.app.data.model.ScheduleResponse
import com.iams.app.data.model.UserResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.LocalTime
import java.util.Calendar
import javax.inject.Inject

data class StudentHomeUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val user: UserResponse? = null,
    val allSchedules: List<ScheduleResponse> = emptyList(),
    val todaySchedules: List<ScheduleResponse> = emptyList(),
    val currentClass: ScheduleResponse? = null,
    val nextClass: ScheduleResponse? = null,
    val faceRegistered: Boolean? = null, // null = loading
    val recentActivity: List<AttendanceRecordResponse> = emptyList(),
    val todayAttendanceMap: Map<String, AttendanceRecordResponse> = emptyMap(),
)

@HiltViewModel
class StudentHomeViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(StudentHomeUiState())
    val uiState: StateFlow<StudentHomeUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    fun loadData() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                val userDeferred = async {
                    try {
                        val response = apiService.getMe()
                        if (response.isSuccessful) response.body() else null
                    } catch (_: Exception) { null }
                }

                val schedulesDeferred = async {
                    try {
                        val response = apiService.getMySchedules()
                        if (response.isSuccessful) response.body() ?: emptyList()
                        else emptyList()
                    } catch (_: Exception) { emptyList() }
                }

                val faceDeferred = async {
                    try {
                        val response = apiService.getFaceStatus()
                        if (response.isSuccessful) response.body()?.faceRegistered
                        else null
                    } catch (_: Exception) { null }
                }

                val activityDeferred = async {
                    try {
                        val response = apiService.getMyAttendance()
                        if (response.isSuccessful) {
                            (response.body() ?: emptyList()).take(5)
                        } else emptyList()
                    } catch (_: Exception) { emptyList() }
                }

                val user = userDeferred.await()
                val allSchedules = schedulesDeferred.await()
                val faceRegistered = faceDeferred.await()
                val recentActivity = activityDeferred.await()

                // Filter today's schedules (backend: 0=Monday)
                val todayBackendDay = todayBackendDayOfWeek()
                val todaySchedules = allSchedules
                    .filter { it.dayOfWeekInt == todayBackendDay }
                    .sortedBy { it.startTime }

                // Determine current and next class
                val now = LocalTime.now()
                val currentClass = todaySchedules.firstOrNull { schedule ->
                    val start = parseTime(schedule.startTime)
                    val end = parseTime(schedule.endTime)
                    start != null && end != null && !now.isBefore(start) && !now.isAfter(end)
                }

                val nextClass = if (currentClass == null) {
                    todaySchedules.firstOrNull { schedule ->
                        val start = parseTime(schedule.startTime)
                        start != null && now.isBefore(start)
                    }
                } else null

                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    user = user,
                    allSchedules = allSchedules,
                    todaySchedules = todaySchedules,
                    currentClass = currentClass,
                    nextClass = nextClass,
                    faceRegistered = faceRegistered,
                    recentActivity = recentActivity,
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
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

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    /**
     * Get the greeting text based on time of day.
     */
    fun getGreeting(): String {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        return when {
            hour < 12 -> "Good morning"
            hour < 18 -> "Good afternoon"
            else -> "Good evening"
        }
    }

    /**
     * Find the next day (after today) that has classes.
     * Returns a pair of (backendDay, schedules) or null.
     */
    fun getNextDayWithClasses(): Pair<Int, List<ScheduleResponse>>? {
        val todayBackend = todayBackendDayOfWeek()
        val allSchedules = _uiState.value.allSchedules
        for (offset in 1..7) {
            val checkDay = (todayBackend + offset) % 7
            val daySchedules = allSchedules.filter {
                it.dayOfWeekInt == checkDay
            }
            if (daySchedules.isNotEmpty()) {
                return Pair(checkDay, daySchedules.sortedBy { it.startTime })
            }
        }
        return null
    }

    /**
     * Find subject info for an attendance record by matching schedule_id.
     */
    fun getScheduleInfoForRecord(record: AttendanceRecordResponse): Pair<String, String> {
        val matched = _uiState.value.allSchedules.find { it.id == record.scheduleId }
        return Pair(
            matched?.subjectName ?: "Class ${record.scheduleId.take(8)}",
            matched?.subjectCode ?: record.scheduleId.take(8)
        )
    }

    /**
     * Convert current system day to backend format (0=Monday, 6=Sunday).
     */
    private fun todayBackendDayOfWeek(): Int {
        // Java DayOfWeek: MONDAY=1 ... SUNDAY=7
        return LocalDate.now().dayOfWeek.value - 1
    }

    /**
     * Parse "HH:MM:SS" or "HH:MM" to LocalTime.
     */
    private fun parseTime(time: String): LocalTime? {
        return try {
            LocalTime.parse(time)
        } catch (_: Exception) {
            try {
                val parts = time.split(":")
                LocalTime.of(parts[0].toInt(), parts[1].toInt())
            } catch (_: Exception) { null }
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
