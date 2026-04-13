package com.iams.app.data.api

import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonParser
import com.iams.app.data.model.AttendanceSummaryMessage
import com.iams.app.data.model.FrameUpdateMessage
import com.iams.app.data.model.TrackInfo
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

/**
 * WebSocket client for real-time attendance tracking.
 *
 * Handles two message types from the backend pipeline:
 * - frame_update:        Per-frame tracking data at ~15fps
 * - attendance_summary:  Periodic attendance state (every 5-10s)
 *
 * Auto-reconnects with exponential backoff using coroutines.
 *
 * @param baseUrl       WebSocket base URL (e.g. ws://host:port/api/v1/ws)
 * @param client        Shared OkHttpClient instance (do NOT shut down in destroy)
 * @param tokenProvider Lambda returning the current JWT access token, or null
 */
class AttendanceWebSocketClient(
    private val baseUrl: String,
    private val client: OkHttpClient,
    private val tokenProvider: () -> String?
) {

    companion object {
        private const val TAG = "AttendanceWS"
        private const val INITIAL_RECONNECT_DELAY = 1000L
        private const val MAX_RECONNECT_DELAY = 15000L
    }

    private var webSocket: WebSocket? = null
    private val gson = Gson()
    private var targetScheduleId: String? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var reconnectJob: Job? = null
    private var reconnectDelay = INITIAL_RECONNECT_DELAY

    // Real-time tracks from frame_update messages
    private val _tracks = MutableStateFlow<List<TrackInfo>>(emptyList())
    val tracks = _tracks.asStateFlow()

    // Frame update metadata
    private val _frameUpdate = MutableStateFlow<FrameUpdateMessage?>(null)
    val frameUpdate = _frameUpdate.asStateFlow()

    // Attendance summary from attendance_summary messages
    private val _attendanceSummary = MutableStateFlow<AttendanceSummaryMessage?>(null)
    val attendanceSummary = _attendanceSummary.asStateFlow()

    // Frame dimensions from backend (width, height)
    private val _frameDimensions = MutableStateFlow(Pair(0, 0))
    val frameDimensions = _frameDimensions.asStateFlow()

    private val _isConnected = MutableStateFlow(false)
    val isConnected = _isConnected.asStateFlow()

    fun connect(scheduleId: String) {
        targetScheduleId = scheduleId
        reconnectJob?.cancel()
        reconnectDelay = INITIAL_RECONNECT_DELAY
        // Close any existing socket before reconnecting
        webSocket?.close(1000, "Reconnecting")
        webSocket = null
        doConnect(scheduleId)
    }

    private fun doConnect(scheduleId: String) {
        val token = tokenProvider.invoke()
        val url = if (token != null) {
            "$baseUrl/attendance/$scheduleId?token=$token"
        } else {
            "$baseUrl/attendance/$scheduleId"
        }

        val request = Request.Builder()
            .url(url)
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(ws: WebSocket, response: Response) {
                _isConnected.value = true
                reconnectDelay = INITIAL_RECONNECT_DELAY
                Log.i(TAG, "Connected to schedule $scheduleId")
            }

            override fun onMessage(ws: WebSocket, text: String) {
                if (text == "pong") return
                try {
                    val json = JsonParser.parseString(text).asJsonObject
                    val type = json.get("type")?.asString ?: return

                    when (type) {
                        "frame_update" -> {
                            val msg = gson.fromJson(text, FrameUpdateMessage::class.java)
                            _frameUpdate.value = msg
                            _tracks.value = msg.tracks
                            msg.frameSize?.let { fs ->
                                if (fs.size >= 2) _frameDimensions.value = Pair(fs[0], fs[1])
                            }
                        }
                        "attendance_summary" -> {
                            val msg = gson.fromJson(text, AttendanceSummaryMessage::class.java)
                            _attendanceSummary.value = msg
                        }
                        // Legacy scan_result — convert to tracks for backward compat
                        "scan_result" -> {
                            val detections = json.getAsJsonArray("detections")
                            val trackInfos = detections?.mapIndexed { idx, det ->
                                val obj = det.asJsonObject
                                val bbox = obj.getAsJsonArray("bbox").map { it.asFloat }
                                TrackInfo(
                                    trackId = idx,
                                    bbox = bbox,
                                    name = obj.get("name")?.takeIf { !it.isJsonNull }?.asString,
                                    confidence = obj.get("confidence")?.asFloat ?: 0f,
                                    userId = obj.get("user_id")?.takeIf { !it.isJsonNull }?.asString,
                                    status = if (obj.get("name")?.takeIf { !it.isJsonNull } != null) "recognized" else "unknown"
                                )
                            } ?: emptyList()
                            _tracks.value = trackInfos
                        }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to parse message: ${e.message}")
                }
            }

            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                _isConnected.value = false
                Log.i(TAG, "WebSocket closed: $reason")
                // Reconnect after server-initiated graceful close
                scheduleReconnect()
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                _isConnected.value = false
                Log.w(TAG, "WebSocket failure: ${t.message}")
                scheduleReconnect()
            }
        })
    }

    private fun scheduleReconnect() {
        val sid = targetScheduleId ?: return
        reconnectJob?.cancel()
        reconnectJob = scope.launch {
            delay(reconnectDelay)
            reconnectDelay = (reconnectDelay * 2).coerceAtMost(MAX_RECONNECT_DELAY)
            Log.i(TAG, "Reconnecting to $sid...")
            doConnect(sid)
        }
    }

    fun disconnect() {
        targetScheduleId = null
        reconnectJob?.cancel()
        webSocket?.close(1000, "Closing")
        webSocket = null
        _isConnected.value = false
        _tracks.value = emptyList()
        _frameUpdate.value = null
        _attendanceSummary.value = null
    }

    fun destroy() {
        disconnect()
        scope.cancel()
    }
}
