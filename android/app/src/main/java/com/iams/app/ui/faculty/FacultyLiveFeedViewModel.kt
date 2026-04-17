package com.iams.app.ui.faculty

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iams.app.BuildConfig
import com.iams.app.data.api.ApiService
import com.iams.app.data.api.AttendanceWebSocketClient
import com.iams.app.data.api.TokenManager
import com.iams.app.data.sync.TimeSyncClient
import com.iams.app.hybrid.FaceIdentityMatcher
import com.iams.app.hybrid.HybridFallbackController
import com.iams.app.hybrid.HybridMode
import com.iams.app.hybrid.HybridTrack
import com.iams.app.ui.debug.DiagnosticMetricsCollector
import com.iams.app.webrtc.MlKitFace
import okhttp3.OkHttpClient
import com.iams.app.data.model.AttendanceSummaryMessage
import com.iams.app.data.model.FrameUpdateMessage
import com.iams.app.data.model.RoomResponse
import com.iams.app.data.model.ScheduleConfigUpdateRequest
import com.iams.app.data.model.ScheduleResponse
import com.iams.app.data.model.SessionStartRequest
import com.iams.app.data.model.StudentAttendanceStatus
import com.iams.app.data.model.TrackInfo
import android.util.Log
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
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
    val earlyLeaveReturnedStudents: List<StudentAttendanceStatus> = emptyList(),
    val presentCount: Int = 0,
    val totalEnrolled: Int = 0,
    val fps: Float = 0f,
    val processingMs: Float = 0f,
    val sessionActive: Boolean = false,
    val sessionLoading: Boolean = false,
    val earlyLeaveTimeoutMinutes: Int = 5,
    val configSaving: Boolean = false,
)

@HiltViewModel
class FacultyLiveFeedViewModel @Inject constructor(
    private val apiService: ApiService,
    private val okHttpClient: OkHttpClient,
    private val tokenManager: TokenManager,
    private val matcher: FaceIdentityMatcher,
    private val timeSync: TimeSyncClient,
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
    val frameDimensions: StateFlow<Pair<Int, Int>> = wsClient.frameDimensions

    // --- Hybrid detection state (master-plan §5, session 06) ---
    // Serialises every matcher call onto one worker thread; matcher is not thread-safe.
    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    private val matcherDispatcher = Dispatchers.Default.limitedParallelism(1)

    /** ML Kit-positioned boxes fused with backend identities. Empty when hybrid disabled. */
    val hybridTracks: StateFlow<List<HybridTrack>> = matcher.tracks

    /** Effective ML Kit frame dimensions after rotation. Fed from the WebRTC sink. */
    private val _mlkitFrameSize = MutableStateFlow(Pair(0, 0))
    val mlkitFrameSize: StateFlow<Pair<Int, Int>> = _mlkitFrameSize.asStateFlow()

    /** Time-sync passthroughs for the HUD (session 04). */
    val timeSyncSkewMs: StateFlow<Long> = timeSync.skewMs
    val timeSyncRttMs: StateFlow<Long> = timeSync.lastRttMs

    // Fallback controller + HUD collector are ViewModel-owned (not Hilt).
    private val fallback = HybridFallbackController(
        matcher = matcher,
        timeSync = timeSync,
        scope = CoroutineScope(SupervisorJob() + Dispatchers.Default),
    )
    val hybridMode: StateFlow<HybridMode> = fallback.mode

    private val metricsCollector = DiagnosticMetricsCollector()
    private val _hudSnapshot = MutableStateFlow(DiagnosticMetricsCollector.Snapshot.EMPTY)
    val hudSnapshot: StateFlow<DiagnosticMetricsCollector.Snapshot> = _hudSnapshot.asStateFlow()

    private var initialized = false

    fun initialize(scheduleId: String, roomId: String) {
        if (initialized) return
        initialized = true
        currentScheduleId = scheduleId

        // Start WebSocket immediately
        wsClient.connect(scheduleId)
        observeWebSocket()

        if (BuildConfig.HYBRID_DETECTION_ENABLED) {
            startHybridPipeline()
        }

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
                    val schedule = response.body()
                    _uiState.value = _uiState.value.copy(
                        schedule = schedule,
                        earlyLeaveTimeoutMinutes = schedule?.earlyLeaveTimeoutMinutes ?: 5,
                    )
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
        // Observe frame updates for real-time stats (and forward to matcher when hybrid on)
        viewModelScope.launch {
            wsClient.frameUpdate.collect { msg ->
                if (msg != null) {
                    _uiState.value = _uiState.value.copy(
                        fps = msg.fps,
                        processingMs = msg.processingMs,
                    )
                    if (BuildConfig.HYBRID_DETECTION_ENABLED) {
                        val nowNs = System.nanoTime()
                        fallback.reportBackendMessage(nowNs)
                        metricsCollector.recordBackend(nowNs, msg.frameSequence)
                        viewModelScope.launch(matcherDispatcher) {
                            matcher.onBackendFrame(msg.tracks, msg.serverTimeMs, nowNs)
                        }
                    }
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

        // Observe WS connection state — matcher + fallback need explicit hard events.
        if (BuildConfig.HYBRID_DETECTION_ENABLED) {
            viewModelScope.launch {
                wsClient.isConnected.collect { connected ->
                    if (connected) fallback.reportWsConnected()
                    else fallback.reportWsDisconnected()
                }
            }
        }
    }

    /**
     * Bring up the hybrid pipeline: start time-sync polling, the fallback controller's ticker,
     * and the HUD snapshot emitter. Called once per session from [initialize].
     */
    private fun startHybridPipeline() {
        // Time-sync client talks to /api/v1/health/time via the shared OkHttpClient.
        val baseUrl = "http://${BuildConfig.BACKEND_HOST}:${BuildConfig.BACKEND_PORT}"
        timeSync.start(baseUrl)
        fallback.start()

        // 2Hz snapshot emitter — feeds the diagnostic HUD. Not CPU-intensive.
        viewModelScope.launch {
            while (isActive) {
                _hudSnapshot.value = metricsCollector.snapshot(
                    tracks = matcher.tracks.value,
                    skewMs = timeSync.skewMs.value,
                    rttMs = timeSync.lastRttMs.value,
                    nowNs = System.nanoTime(),
                )
                delay(HUD_SNAPSHOT_INTERVAL_MS)
            }
        }
    }

    /** Called by [NativeWebRtcVideoPlayer]'s onMlKitFacesUpdate callback (session 02). */
    fun onMlKitFaces(faces: List<MlKitFace>) {
        if (!BuildConfig.HYBRID_DETECTION_ENABLED) return
        val nowNs = System.nanoTime()
        // Always report liveness so the fallback controller sees the sink is alive even if
        // the face list is empty (covered-camera case must NOT trigger BACKEND_ONLY).
        fallback.reportMlkitUpdate(nowNs)
        metricsCollector.recordMlkit(nowNs)
        viewModelScope.launch(matcherDispatcher) {
            matcher.onMlKitUpdate(faces, nowNs)
        }
    }

    /** Called by [NativeWebRtcVideoPlayer]'s onMlKitFrameSize callback (session 02). */
    fun onMlKitFrameSize(width: Int, height: Int) {
        if (!BuildConfig.HYBRID_DETECTION_ENABLED) return
        _mlkitFrameSize.value = width to height
    }

    private fun updateFromAttendanceSummary(summary: AttendanceSummaryMessage) {
        val present = summary.present?.map { toStudentStatus(it.userId, it.name, "present") } ?: emptyList()
        val absent = summary.absent?.map { toStudentStatus(it.userId, it.name, "absent") } ?: emptyList()
        val late = summary.late?.map { toStudentStatus(it.userId, it.name, "late") } ?: emptyList()
        val earlyLeave = summary.earlyLeave?.map { toStudentStatus(it.userId, it.name, "early_leave") } ?: emptyList()
        val earlyLeaveReturned = summary.earlyLeaveReturned?.map { toStudentStatus(it.userId, it.name, "returned") } ?: emptyList()

        _uiState.value = _uiState.value.copy(
            presentStudents = present,
            absentStudents = absent,
            lateStudents = late,
            earlyLeaveStudents = earlyLeave,
            earlyLeaveReturnedStudents = earlyLeaveReturned,
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
            _uiState.value = _uiState.value.copy(sessionLoading = true, error = null)
            try {
                val response = apiService.startSession(SessionStartRequest(currentScheduleId))
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        sessionActive = true,
                        sessionLoading = false
                    )
                } else {
                    val msg = response.errorBody()?.string() ?: "Failed to start session"
                    _uiState.value = _uiState.value.copy(
                        sessionLoading = false,
                        error = msg
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    sessionLoading = false,
                    error = "Network error — could not start session"
                )
            }
        }
    }

    fun endSession() {
        if (currentScheduleId.isEmpty()) return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(sessionLoading = true, error = null)
            try {
                val response = apiService.endSession(currentScheduleId)
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        sessionActive = false,
                        sessionLoading = false
                    )
                } else {
                    val msg = response.errorBody()?.string() ?: "Failed to end session"
                    _uiState.value = _uiState.value.copy(
                        sessionLoading = false,
                        error = msg
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    sessionLoading = false,
                    error = "Network error — could not end session"
                )
            }
        }
    }

    fun updateEarlyLeaveTimeout(minutes: Int) {
        if (currentScheduleId.isEmpty()) return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(configSaving = true)
            try {
                val response = apiService.updateScheduleConfig(
                    currentScheduleId,
                    ScheduleConfigUpdateRequest(minutes)
                )
                if (response.isSuccessful) {
                    _uiState.value = _uiState.value.copy(
                        earlyLeaveTimeoutMinutes = minutes,
                        configSaving = false,
                    )
                } else {
                    _uiState.value = _uiState.value.copy(configSaving = false)
                }
            } catch (_: Exception) {
                _uiState.value = _uiState.value.copy(configSaving = false)
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        wsClient.destroy()
        if (BuildConfig.HYBRID_DETECTION_ENABLED) {
            fallback.stop()
            timeSync.stop()
            viewModelScope.launch(matcherDispatcher) { matcher.reset() }
        }
    }

    companion object {
        private const val HUD_SNAPSHOT_INTERVAL_MS = 500L
    }
}
