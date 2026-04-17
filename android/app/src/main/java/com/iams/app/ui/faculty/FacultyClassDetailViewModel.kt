package com.iams.app.ui.faculty

import androidx.lifecycle.SavedStateHandle
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
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import javax.inject.Inject

data class FacultyClassDetailUiState(
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val error: String? = null,
    val classData: LiveAttendanceResponse? = null,
    val students: List<StudentAttendanceStatus> = emptyList(),
    val presentCount: Int = 0,
    val lateCount: Int = 0,
    val absentCount: Int = 0,
    val earlyLeaveCount: Int = 0,
    val isSessionActive: Boolean = false,
)

@HiltViewModel
class FacultyClassDetailViewModel @Inject constructor(
    private val apiService: ApiService,
    private val tokenManager: TokenManager,
    private val okHttpClient: OkHttpClient,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    val scheduleId: String = savedStateHandle["scheduleId"] ?: ""
    val date: String = savedStateHandle["date"] ?: ""

    private val _uiState = MutableStateFlow(FacultyClassDetailUiState())
    val uiState: StateFlow<FacultyClassDetailUiState> = _uiState.asStateFlow()

    private var wsClient: AttendanceWebSocketClient? = null
    private var wsObserverJob: Job? = null

    init {
        loadClassDetails()
    }

    fun loadClassDetails(silent: Boolean = false) {
        viewModelScope.launch {
            if (!silent) {
                _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            }
            try {
                val response = apiService.getLiveAttendance(scheduleId)
                if (response.isSuccessful) {
                    val data = response.body()
                    val sessionActive = data?.sessionActive ?: false
                    _uiState.value = _uiState.value.copy(
                        classData = data,
                        students = data?.students ?: emptyList(),
                        presentCount = data?.presentCount ?: 0,
                        lateCount = data?.lateCount ?: 0,
                        absentCount = data?.absentCount ?: 0,
                        earlyLeaveCount = data?.earlyLeaveCount ?: 0,
                        isSessionActive = sessionActive,
                        isLoading = false,
                        isRefreshing = false,
                        error = null,
                    )
                    // Start WebSocket if session is active for real-time updates
                    if (sessionActive && wsClient == null) {
                        startWebSocket()
                    }
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        error = "Failed to load class details",
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = "Unable to load class details. Please try again.",
                )
            }
        }
    }

    private fun startWebSocket() {
        wsObserverJob?.cancel()
        wsClient?.disconnect()

        wsClient = AttendanceWebSocketClient(
            "ws://${BuildConfig.BACKEND_HOST}:${BuildConfig.BACKEND_PORT}/api/v1/ws",
            okHttpClient,
            { tokenManager.accessToken }
        )
        wsClient?.connect(scheduleId)

        wsObserverJob = viewModelScope.launch {
            wsClient?.attendanceSummary?.collect { msg ->
                if (msg != null) {
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
                        students = students,
                        presentCount = msg.onTimeCount,
                        lateCount = msg.lateCount,
                        absentCount = msg.absentCount,
                        earlyLeaveCount = msg.earlyLeaveCount,
                    )
                }
            }
        }
    }

    fun refresh() {
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        loadClassDetails(silent = true)
    }

    override fun onCleared() {
        super.onCleared()
        wsObserverJob?.cancel()
        wsClient?.disconnect()
    }
}
