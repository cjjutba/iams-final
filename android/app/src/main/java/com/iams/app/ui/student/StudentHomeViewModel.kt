package com.iams.app.ui.student

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.NotificationService
import com.iams.app.data.api.PendingFaceUploadManager
import com.iams.app.data.api.TokenManager
import com.iams.app.data.model.AttendanceRecordResponse
import com.iams.app.data.model.AttendanceSummaryResponse
import com.iams.app.data.model.ScheduleResponse
import com.iams.app.data.model.UserResponse
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.Duration
import java.time.LocalDate
import java.time.LocalTime
import java.util.Calendar
import javax.inject.Inject

enum class ScheduleTimeState { COMPLETED, ACTIVE, UPCOMING }

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
    val faceUploading: Boolean = false,
    val recentActivity: List<AttendanceRecordResponse> = emptyList(),
    val todayAttendanceMap: Map<String, AttendanceRecordResponse> = emptyMap(),
    val unreadNotificationCount: Int = 0,
    val attendanceSummary: AttendanceSummaryResponse? = null,
)

@HiltViewModel
class StudentHomeViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager,
    val notificationService: NotificationService,
    private val pendingFaceUploadManager: PendingFaceUploadManager,
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

                val unreadCountDeferred = async {
                    try {
                        notificationService.fetchUnreadCount(apiService)
                        notificationService.unreadCount.value
                    } catch (_: Exception) { 0 }
                }

                val summaryDeferred = async {
                    try {
                        val response = apiService.getMyAttendanceSummary()
                        if (response.isSuccessful) response.body() else null
                    } catch (_: Exception) { null }
                }

                val user = userDeferred.await()
                val allSchedules = schedulesDeferred.await()
                var faceRegistered = faceDeferred.await()
                val recentActivity = activityDeferred.await()
                val unreadCount = unreadCountDeferred.await()
                val summary = summaryDeferred.await()

                // If face not registered but there are pending uploads from registration,
                // upload them first, then re-check status
                if (faceRegistered != true && pendingFaceUploadManager.hasPendingFaces()) {
                    _uiState.value = _uiState.value.copy(faceUploading = true)
                    val uploaded = pendingFaceUploadManager.uploadPendingFaces()
                    if (uploaded) {
                        // Re-check face status after successful upload
                        faceRegistered = try {
                            val response = apiService.getFaceStatus()
                            if (response.isSuccessful) response.body()?.faceRegistered else faceRegistered
                        } catch (_: Exception) { faceRegistered }
                    }
                }

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

                // Build today's attendance map from recent activity
                val todayStr = LocalDate.now().toString()
                val todayAttMap = recentActivity
                    .filter { it.date == todayStr }
                    .associateBy { it.scheduleId }

                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    user = user,
                    allSchedules = allSchedules,
                    todaySchedules = todaySchedules,
                    currentClass = currentClass,
                    nextClass = nextClass,
                    faceRegistered = faceRegistered,
                    faceUploading = false,
                    recentActivity = recentActivity,
                    todayAttendanceMap = todayAttMap,
                    unreadNotificationCount = unreadCount,
                    attendanceSummary = summary,
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = "Failed to load data. Pull to refresh."
                )
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true, error = null)
        loadData()
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

    fun getMinutesUntilStart(schedule: ScheduleResponse): Long {
        val start = parseTime(schedule.startTime) ?: return 0
        return Duration.between(LocalTime.now(), start).toMinutes().coerceAtLeast(0)
    }

    fun formatTime(timeStr: String): String {
        val time = parseTime(timeStr) ?: return timeStr
        return try {
            val hours = time.hour
            val minutes = time.minute
            val period = if (hours >= 12) "PM" else "AM"
            val displayHours = if (hours % 12 == 0) 12 else hours % 12
            "$displayHours:${minutes.toString().padStart(2, '0')} $period"
        } catch (_: Exception) { timeStr }
    }

    /**
     * Get today's attendance status for a given schedule.
     */
    fun getTodayStatus(scheduleId: String): String? {
        return _uiState.value.todayAttendanceMap[scheduleId]?.status
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
