package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.BuildConfig
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.AttendanceWebSocketClient
import com.iams.app.data.api.TokenManager
import com.iams.app.data.model.LiveAttendanceResponse
import com.iams.app.data.model.StudentAttendanceStatus
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import javax.inject.Inject

data class FacultyLiveAttendanceUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val liveAttendance: LiveAttendanceResponse? = null,
    val roomId: String = "",
    val searchQuery: String = "",
    val isSessionActive: Boolean = false,
    val isEndingSession: Boolean = false,
    val isConnected: Boolean = true,
) {
    val filteredStudents: List<StudentAttendanceStatus>
        get() {
            val students = liveAttendance?.students ?: emptyList()
            if (searchQuery.isBlank()) return students
            val query = searchQuery.lowercase()
            return students.filter { student ->
                student.studentName.lowercase().contains(query) ||
                    student.studentId.lowercase().contains(query) ||
                    (student.studentNumber?.lowercase()?.contains(query) == true)
            }
        }

    val presentCount: Int get() = liveAttendance?.presentCount ?: 0
    val lateCount: Int get() = liveAttendance?.lateCount ?: 0
    val absentCount: Int get() = liveAttendance?.absentCount ?: 0
    val earlyLeaveCount: Int get() = liveAttendance?.earlyLeaveCount ?: 0
}

@HiltViewModel
class FacultyLiveAttendanceViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager,
    private val okHttpClient: OkHttpClient,
) : ViewModel() {

    private val _uiState = MutableStateFlow(FacultyLiveAttendanceUiState())
    val uiState: StateFlow<FacultyLiveAttendanceUiState> = _uiState.asStateFlow()

    private var pollingJob: Job? = null
    private var wsClient: AttendanceWebSocketClient? = null
    private var wsObserverJob: Job? = null
    private var currentScheduleId: String? = null

    fun initialize(scheduleId: String) {
        if (currentScheduleId == scheduleId) return
        currentScheduleId = scheduleId
        loadData(scheduleId)
        loadScheduleRoomId(scheduleId)
        checkSessionStatus(scheduleId)
        startWebSocket(scheduleId)
        startPolling(scheduleId)
    }

    private fun loadScheduleRoomId(scheduleId: String) {
        viewModelScope.launch {
            try {
                val response = apiService.getSchedule(scheduleId)
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        roomId = response.body()?.roomId ?: ""
                    )
                }
            } catch (_: Exception) { /* roomId stays empty — live feed will degrade gracefully */ }
        }
    }

    fun loadData(scheduleId: String? = currentScheduleId) {
        val id = scheduleId ?: return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                val response = apiService.getLiveAttendance(id)
                if (response.isSuccessful) {
                    val body = response.body()
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        liveAttendance = body,
                        isSessionActive = body?.sessionActive ?: _uiState.value.isSessionActive,
                        isConnected = true,
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Unable to load live attendance. Please try again."
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isConnected = false,
                    error = "Unable to load live attendance. Please try again."
                )
            }
        }
    }

    private fun checkSessionStatus(scheduleId: String) {
        viewModelScope.launch {
            try {
                val response = apiService.getActiveSessions()
                if (response.isSuccessful) {
                    val active = response.body()?.activeSessions ?: emptyList()
                    _uiState.value = _uiState.value.copy(
                        isSessionActive = active.contains(scheduleId)
                    )
                }
            } catch (_: Exception) {}
        }
    }

    private fun startWebSocket(scheduleId: String) {
        wsObserverJob?.cancel()
        wsClient?.disconnect()

        wsClient = AttendanceWebSocketClient(
            "ws://${BuildConfig.BACKEND_HOST}:${BuildConfig.BACKEND_PORT}/api/v1/ws",
            okHttpClient,
            { tokenManager.accessToken }
        )
        wsClient?.connect(scheduleId)

        // Observe attendance_summary from WebSocket for real-time updates
        wsObserverJob = viewModelScope.launch {
            wsClient?.attendanceSummary?.collect { msg ->
                if (msg != null) {
                    // Build student list from WS summary lists
                    val students = mutableListOf<StudentAttendanceStatus>()
                    msg.present?.forEach {
                        students.add(StudentAttendanceStatus(studentId = it.userId, studentName = it.name, status = "present"))
                    }
                    msg.late?.forEach {
                        students.add(StudentAttendanceStatus(studentId = it.userId, studentName = it.name, status = "late"))
                    }
                    msg.earlyLeave?.forEach {
                        students.add(StudentAttendanceStatus(studentId = it.userId, studentName = it.name, status = "early_leave"))
                    }
                    msg.earlyLeaveReturned?.forEach {
                        students.add(StudentAttendanceStatus(studentId = it.userId, studentName = it.name, status = "returned"))
                    }
                    msg.absent?.forEach {
                        students.add(StudentAttendanceStatus(studentId = it.userId, studentName = it.name, status = "absent"))
                    }

                    _uiState.value = _uiState.value.copy(
                        liveAttendance = LiveAttendanceResponse(
                            scheduleId = msg.scheduleId,
                            totalEnrolled = msg.totalEnrolled,
                            presentCount = msg.onTimeCount,
                            lateCount = msg.lateCount,
                            absentCount = msg.absentCount,
                            earlyLeaveCount = msg.earlyLeaveCount,
                            sessionActive = true,
                            students = students,
                        ),
                        isConnected = true,
                        isSessionActive = true,
                    )
                }
            }
        }
    }

    private fun startPolling(scheduleId: String) {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            while (isActive) {
                delay(30_000)
                try {
                    val response = apiService.getLiveAttendance(scheduleId)
                    if (response.isSuccessful) {
                        val body = response.body()
                        _uiState.value = _uiState.value.copy(
                            liveAttendance = body,
                            isSessionActive = body?.sessionActive ?: _uiState.value.isSessionActive,
                            isConnected = true,
                        )
                    }
                } catch (_: Exception) {
                    _uiState.value = _uiState.value.copy(isConnected = false)
                }
            }
        }
    }

    fun refresh() {
        val id = currentScheduleId ?: return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRefreshing = true)
            try {
                val response = apiService.getLiveAttendance(id)
                if (response.isSuccessful) {
                    val body = response.body()
                    _uiState.value = _uiState.value.copy(
                        liveAttendance = body,
                        isSessionActive = body?.sessionActive ?: _uiState.value.isSessionActive,
                        isConnected = true,
                    )
                }
            } catch (_: Exception) {
                _uiState.value = _uiState.value.copy(isConnected = false)
            }
            _uiState.value = _uiState.value.copy(isRefreshing = false)
        }
    }

    fun updateSearchQuery(query: String) {
        _uiState.value = _uiState.value.copy(searchQuery = query)
    }

    fun endSession(onSuccess: () -> Unit, onError: (String) -> Unit) {
        val id = currentScheduleId ?: return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isEndingSession = true)
            try {
                val response = apiService.endSession(id)
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        isEndingSession = false,
                        isSessionActive = false,
                    )
                    onSuccess()
                } else {
                    _uiState.value = _uiState.value.copy(isEndingSession = false)
                    onError("Failed to end session")
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isEndingSession = false)
                onError(e.message ?: "Failed to end session")
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        pollingJob?.cancel()
        wsObserverJob?.cancel()
        wsClient?.disconnect()
    }
}
