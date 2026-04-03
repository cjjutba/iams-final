package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.BuildConfig
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.AttendanceWebSocketClient
import com.iams.app.data.api.TokenManager
import okhttp3.OkHttpClient
import com.iams.app.data.model.AttendanceSummaryMessage
import com.iams.app.data.model.FrameUpdateMessage
import com.iams.app.data.model.RoomResponse
import com.iams.app.data.model.ScheduleResponse
import com.iams.app.data.model.SessionStartRequest
import com.iams.app.data.model.StudentAttendanceStatus
import com.iams.app.data.model.TrackInfo
import android.util.Log
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LiveFeedUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val videoError: String? = null,
    val schedule: ScheduleResponse? = null,
    val room: RoomResponse? = null,
    val videoUrl: String = "",
    val presentStudents: List<StudentAttendanceStatus> = emptyList(),
    val absentStudents: List<StudentAttendanceStatus> = emptyList(),
    val lateStudents: List<StudentAttendanceStatus> = emptyList(),
    val earlyLeaveStudents: List<StudentAttendanceStatus> = emptyList(),
    val presentCount: Int = 0,
    val totalEnrolled: Int = 0,
    val fps: Float = 0f,
    val processingMs: Float = 0f,
    val sessionActive: Boolean = false,
    val sessionLoading: Boolean = false,
)

@HiltViewModel
class FacultyLiveFeedViewModel @Inject constructor(
    private val apiService: ApiService,
    private val okHttpClient: OkHttpClient,
    private val tokenManager: TokenManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(LiveFeedUiState())
    val uiState: StateFlow<LiveFeedUiState> = _uiState.asStateFlow()

    // Real-time tracks from WebSocket (replaces localFaces + recognitions)
    private val wsClient = AttendanceWebSocketClient(
        "ws://${BuildConfig.BACKEND_HOST}:${BuildConfig.BACKEND_PORT}/api/v1/ws",
        okHttpClient,
        { tokenManager.accessToken }
    )
    val tracks: StateFlow<List<TrackInfo>> = wsClient.tracks
    val wsConnected: StateFlow<Boolean> = wsClient.isConnected

    private var initialized = false

    fun initialize(scheduleId: String, roomId: String) {
        if (initialized) return
        initialized = true
        currentScheduleId = scheduleId

        // Start WebSocket immediately
        wsClient.connect(scheduleId)
        observeWebSocket()

        // Check if session is already active
        viewModelScope.launch {
            try {
                val response = apiService.getActiveSessions()
                if (response.isSuccessful) {
                    val active = response.body()?.activeSessions ?: emptyList()
                    _uiState.value = _uiState.value.copy(
                        sessionActive = active.contains(scheduleId)
                    )
                }
            } catch (_: Exception) {}
        }

        // Fetch room info (needed for RTSP URL)
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                val response = apiService.getRooms()
                if (response.isSuccessful) {
                    val rooms = response.body() ?: emptyList()
                    val room = rooms.find { it.id == roomId }
                    if (room != null) {
                        // Use mediamtx WHEP player for WebRTC playback (sub-second latency).
                        val url = when {
                            room.streamKey != null ->
                                "http://${BuildConfig.BACKEND_HOST}:${BuildConfig.MEDIAMTX_WEBRTC_PORT}/${room.streamKey}/whep"
                            else -> ""
                        }
                        Log.i("LiveFeed", "WebRTC URL: $url (streamKey=${room.streamKey})")
                        _uiState.value = _uiState.value.copy(
                            room = room,
                            videoUrl = url,
                            isLoading = false
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(isLoading = false)
                    }
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Failed to load room info"
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Failed to load live feed data"
                )
            }
        }

        // Fetch schedule info in parallel
        viewModelScope.launch {
            try {
                val response = apiService.getSchedule(scheduleId)
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(schedule = response.body())
                }
            } catch (_: Exception) {}
        }

        // Fetch initial live attendance in parallel
        viewModelScope.launch {
            try {
                val response = apiService.getLiveAttendance(scheduleId)
                if (response.isSuccessful) {
                    response.body()?.let { live ->
                        val present = live.present ?: emptyList()
                        val absent = live.absent ?: emptyList()
                        val late = live.late ?: emptyList()
                        val earlyLeave = live.earlyLeave ?: emptyList()
                        _uiState.value = _uiState.value.copy(
                            presentStudents = present,
                            absentStudents = absent,
                            lateStudents = late,
                            earlyLeaveStudents = earlyLeave,
                            presentCount = present.size + late.size,
                            totalEnrolled = present.size + absent.size + late.size + earlyLeave.size
                        )
                    }
                }
            } catch (_: Exception) {}
        }
    }

    private fun observeWebSocket() {
        // Observe frame updates for real-time stats
        viewModelScope.launch {
            wsClient.frameUpdate.collect { msg ->
                if (msg != null) {
                    _uiState.value = _uiState.value.copy(
                        fps = msg.fps,
                        processingMs = msg.processingMs,
                    )
                }
            }
        }

        // Observe attendance summaries
        viewModelScope.launch {
            wsClient.attendanceSummary.collect { msg ->
                if (msg != null) {
                    updateFromAttendanceSummary(msg)
                }
            }
        }
    }

    private fun updateFromAttendanceSummary(summary: AttendanceSummaryMessage) {
        val present = summary.present?.map { toStudentStatus(it.userId, it.name, "present") } ?: emptyList()
        val absent = summary.absent?.map { toStudentStatus(it.userId, it.name, "absent") } ?: emptyList()
        val late = summary.late?.map { toStudentStatus(it.userId, it.name, "late") } ?: emptyList()
        val earlyLeave = summary.earlyLeave?.map { toStudentStatus(it.userId, it.name, "early_leave") } ?: emptyList()

        _uiState.value = _uiState.value.copy(
            presentStudents = present,
            absentStudents = absent,
            lateStudents = late,
            earlyLeaveStudents = earlyLeave,
            presentCount = summary.presentCount,
            totalEnrolled = summary.totalEnrolled,
        )
    }

    private fun toStudentStatus(userId: String, name: String, status: String) =
        StudentAttendanceStatus(
            studentId = userId,
            studentName = name,
            status = status,
        )

    fun onVideoError(error: String) {
        _uiState.value = _uiState.value.copy(videoError = error)
    }

    private var currentScheduleId: String = ""

    fun startSession() {
        if (currentScheduleId.isEmpty()) return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(sessionLoading = true)
            try {
                val response = apiService.startSession(SessionStartRequest(currentScheduleId))
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        sessionActive = true,
                        sessionLoading = false
                    )
                } else {
                    _uiState.value = _uiState.value.copy(sessionLoading = false)
                }
            } catch (_: Exception) {
                _uiState.value = _uiState.value.copy(sessionLoading = false)
            }
        }
    }

    fun endSession() {
        if (currentScheduleId.isEmpty()) return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(sessionLoading = true)
            try {
                val response = apiService.endSession(currentScheduleId)
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        sessionActive = false,
                        sessionLoading = false
                    )
                } else {
                    _uiState.value = _uiState.value.copy(sessionLoading = false)
                }
            } catch (_: Exception) {
                _uiState.value = _uiState.value.copy(sessionLoading = false)
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        wsClient.destroy()
    }
}
