package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.AttendanceWebSocketClient
import com.iams.app.data.model.Detection
import com.iams.app.data.model.LiveAttendanceResponse
import com.iams.app.data.model.RoomResponse
import com.iams.app.data.model.ScheduleResponse
import com.iams.app.data.model.ScanResultMessage
import com.iams.app.data.model.StudentAttendanceStatus
import com.iams.app.ui.components.DetectedFaceLocal
import com.iams.app.ui.components.FaceDetectionProcessor
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LiveFeedUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val schedule: ScheduleResponse? = null,
    val room: RoomResponse? = null,
    val rtspUrl: String = "",
    val presentStudents: List<StudentAttendanceStatus> = emptyList(),
    val absentStudents: List<StudentAttendanceStatus> = emptyList(),
    val lateStudents: List<StudentAttendanceStatus> = emptyList(),
    val earlyLeaveStudents: List<StudentAttendanceStatus> = emptyList(),
    val presentCount: Int = 0,
    val totalEnrolled: Int = 0,
)

@HiltViewModel
class FacultyLiveFeedViewModel @Inject constructor(
    private val apiService: ApiService
) : ViewModel() {

    private val _uiState = MutableStateFlow(LiveFeedUiState())
    val uiState: StateFlow<LiveFeedUiState> = _uiState.asStateFlow()

    val faceProcessor = FaceDetectionProcessor()
    val localFaces: StateFlow<List<DetectedFaceLocal>> = faceProcessor.detectedFaces

    private val wsClient = AttendanceWebSocketClient("ws://167.71.217.44:8000/api/v1/ws")
    val recognitions: StateFlow<List<Detection>> = wsClient.detections
    val wsConnected: StateFlow<Boolean> = wsClient.isConnected

    private var initialized = false

    fun initialize(scheduleId: String, roomId: String) {
        if (initialized) return
        initialized = true

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                // Fetch schedule info
                val scheduleJob = viewModelScope.launch {
                    try {
                        val response = apiService.getSchedule(scheduleId)
                        if (response.isSuccessful) {
                            _uiState.value = _uiState.value.copy(schedule = response.body())
                        }
                    } catch (_: Exception) {}
                }

                // Fetch room info to get stream_key for RTSP URL
                val roomJob = viewModelScope.launch {
                    try {
                        val response = apiService.getRooms()
                        if (response.isSuccessful) {
                            val rooms = response.body() ?: emptyList()
                            val room = rooms.find { it.id == roomId }
                            if (room != null) {
                                _uiState.value = _uiState.value.copy(
                                    room = room,
                                    rtspUrl = if (room.streamKey != null) {
                                        "rtsp://167.71.217.44:8554/${room.streamKey}/raw"
                                    } else ""
                                )
                            }
                        }
                    } catch (_: Exception) {}
                }

                // Fetch initial live attendance
                val attendanceJob = viewModelScope.launch {
                    try {
                        val response = apiService.getLiveAttendance(scheduleId)
                        if (response.isSuccessful) {
                            val live = response.body()
                            if (live != null) {
                                updateAttendanceFromLive(live)
                            }
                        }
                    } catch (_: Exception) {}
                }

                scheduleJob.join()
                roomJob.join()
                attendanceJob.join()

                _uiState.value = _uiState.value.copy(isLoading = false)

                // Connect WebSocket and observe scan results
                wsClient.connect(scheduleId)
                observeScanResults()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = "Failed to load live feed data"
                )
            }
        }
    }

    private fun observeScanResults() {
        viewModelScope.launch {
            wsClient.scanResults.collect { msg ->
                if (msg != null) {
                    _uiState.value = _uiState.value.copy(
                        presentCount = msg.presentCount,
                        totalEnrolled = msg.totalEnrolled
                    )
                    // Refresh full attendance list periodically
                    refreshAttendance(msg.scheduleId)
                }
            }
        }
    }

    private suspend fun refreshAttendance(scheduleId: String) {
        try {
            val response = apiService.getLiveAttendance(scheduleId)
            if (response.isSuccessful) {
                val live = response.body()
                if (live != null) {
                    updateAttendanceFromLive(live)
                }
            }
        } catch (_: Exception) {}
    }

    private fun updateAttendanceFromLive(live: LiveAttendanceResponse) {
        _uiState.value = _uiState.value.copy(
            presentStudents = live.present,
            absentStudents = live.absent,
            lateStudents = live.late,
            earlyLeaveStudents = live.earlyLeave,
            presentCount = live.present.size + live.late.size,
            totalEnrolled = live.present.size + live.absent.size +
                    live.late.size + live.earlyLeave.size
        )
    }

    override fun onCleared() {
        super.onCleared()
        wsClient.disconnect()
        faceProcessor.close()
    }
}
