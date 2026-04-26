package com.iams.app.data.api

import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.iams.app.data.model.NotificationEvent
import com.iams.app.data.model.StudentAttendanceEvent
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

/**
 * WebSocket client for `/api/v1/ws/alerts/{user_id}?token={jwt}`.
 *
 * Dispatches incoming messages by their top-level `type` envelope:
 * - `type: "notification"` → [notificationEvents] as [NotificationEvent]
 * - `type: "attendance_event"` → [attendanceEvents] as [StudentAttendanceEvent]
 * - anything else → logged and ignored (forward-compat)
 *
 * Auto-reconnects with exponential backoff using coroutines. The client is
 * safe to reconnect repeatedly; each `connect()` call cancels any prior
 * reconnect attempt and starts fresh.
 *
 * @param baseUrl         WebSocket base URL (e.g. ws://host:port/api/v1/ws)
 * @param client          Shared OkHttpClient instance
 * @param tokenProvider   Lambda returning the current JWT access token, or null
 * @param userIdProvider  Lambda returning the current user ID, or null
 * @param onConnected     Called on every successful connect/reconnect. Passed
 *                        `disconnectedForMillis` so callers can decide whether
 *                        to fire a catch-up refresh (0 on first connect).
 */
class NotificationWebSocketClient(
    private val baseUrl: String,
    private val client: OkHttpClient,
    private val tokenProvider: () -> String?,
    private val userIdProvider: () -> String?,
    private val onConnected: ((disconnectedForMillis: Long) -> Unit)? = null,
) {

    companion object {
        private const val TAG = "NotificationWS"
        private const val INITIAL_RECONNECT_DELAY = 1000L
        private const val MAX_RECONNECT_DELAY = 15000L
    }

    private var webSocket: WebSocket? = null
    private val gson = Gson()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var reconnectJob: Job? = null
    private var reconnectDelay = INITIAL_RECONNECT_DELAY
    private var lastDisconnectMillis: Long = 0L

    private val _notificationEvents = MutableSharedFlow<NotificationEvent>(
        replay = 0,
        extraBufferCapacity = 20,
    )
    val notificationEvents: SharedFlow<NotificationEvent> = _notificationEvents.asSharedFlow()

    /** Back-compat alias. Existing callers collect `client.events`. */
    val events: SharedFlow<NotificationEvent> get() = notificationEvents

    private val _attendanceEvents = MutableSharedFlow<StudentAttendanceEvent>(
        replay = 0,
        extraBufferCapacity = 32,
    )
    val attendanceEvents: SharedFlow<StudentAttendanceEvent> = _attendanceEvents.asSharedFlow()

    private val _isConnected = MutableStateFlow(false)
    val isConnected = _isConnected.asStateFlow()

    fun connect() {
        reconnectJob?.cancel()
        reconnectDelay = INITIAL_RECONNECT_DELAY
        webSocket?.close(1000, "Reconnecting")
        webSocket = null
        doConnect()
    }

    private fun doConnect() {
        val userId = userIdProvider.invoke()
        val token = tokenProvider.invoke()

        if (userId.isNullOrBlank()) {
            Log.w(TAG, "Cannot connect: no userId available")
            return
        }

        val url = if (token != null) {
            "$baseUrl/alerts/$userId?token=$token"
        } else {
            "$baseUrl/alerts/$userId"
        }

        val request = Request.Builder()
            .url(url)
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(ws: WebSocket, response: Response) {
                _isConnected.value = true
                reconnectDelay = INITIAL_RECONNECT_DELAY
                val gap = if (lastDisconnectMillis > 0L) {
                    System.currentTimeMillis() - lastDisconnectMillis
                } else 0L
                lastDisconnectMillis = 0L
                Log.i(TAG, "Connected to alerts for user $userId (gap=${gap}ms)")
                onConnected?.invoke(gap)
            }

            override fun onMessage(ws: WebSocket, text: String) {
                if (text == "pong") return
                // Stamp the receive time *before* JSON parsing so the
                // latency sample reflects only wire delay, not parser
                // jitter. Backend stamps ``server_time_ms`` on
                // attendance_event payloads (epoch ms at broadcast); the
                // delta is the wire+render side of the
                // detection-to-display SLA in thesis Objective 2.
                val receivedAtMs = System.currentTimeMillis()
                try {
                    val json = JsonParser.parseString(text).asJsonObject
                    when (val type = json.get("type")?.asString) {
                        "notification" -> dispatchNotification(text)
                        "attendance_event" -> {
                            recordE2ELatency(json, receivedAtMs)
                            dispatchAttendanceEvent(json)
                        }
                        null -> Log.w(TAG, "Message without type field ignored")
                        else -> Log.d(TAG, "Ignoring unknown envelope type=$type")
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to parse WS message: ${e.message}")
                }
            }

            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                _isConnected.value = false
                if (lastDisconnectMillis == 0L) lastDisconnectMillis = System.currentTimeMillis()
                Log.i(TAG, "WebSocket closed: $reason")
                scheduleReconnect()
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                _isConnected.value = false
                if (lastDisconnectMillis == 0L) lastDisconnectMillis = System.currentTimeMillis()
                Log.w(TAG, "WebSocket failure: ${t.message}")
                scheduleReconnect()
            }
        })
    }

    /**
     * Log end-to-end latency for the student-facing attendance_event
     * channel (thesis Objective 2). The backend stamps
     * ``server_time_ms`` (epoch ms) at the broadcast moment, and we
     * stamp ``receivedAtMs`` the instant onMessage fires. The delta
     * captures wire + parse + dispatch overhead — i.e. everything that
     * happens between the server committing the event and the client
     * being ready to render it. The full pipeline (frame grab → event)
     * is measured separately on the admin per-frame channel.
     *
     * Output goes to logcat with a stable ``[E2E]`` tag so a thesis
     * data-collection script can grep ``adb logcat`` and dump samples
     * to CSV without needing on-device persistence.
     */
    private fun recordE2ELatency(json: JsonObject, receivedAtMs: Long) {
        val serverMsElement = json.get("server_time_ms") ?: return
        if (serverMsElement.isJsonNull) return
        val serverMs = serverMsElement.asLong
        val deltaMs = receivedAtMs - serverMs
        val event = json.get("event")?.takeUnless { it.isJsonNull }?.asString ?: "unknown"
        val schedule = json.get("schedule_id")?.takeUnless { it.isJsonNull }?.asString?.take(8) ?: "-"
        // Tag-prefixed so `adb logcat -s NotificationWS:* | grep '\[E2E\]'`
        // produces a clean sample stream. The CSV columns mirror the
        // admin probe so both sides plot on the same axes.
        Log.i(
            TAG,
            "[E2E] event=$event schedule=$schedule server_time_ms=$serverMs " +
                "received_at_ms=$receivedAtMs latency_ms=$deltaMs",
        )
    }

    private fun dispatchNotification(raw: String) {
        runCatching {
            val event = gson.fromJson(raw, NotificationEvent::class.java)
            _notificationEvents.tryEmit(event)
            Log.d(TAG, "Notification event: ${event.title}")
        }.onFailure {
            Log.e(TAG, "Failed to parse notification: ${it.message}")
        }
    }

    private fun dispatchAttendanceEvent(json: JsonObject) {
        val eventName = json.get("event")?.asString ?: return
        val scheduleId = json.get("schedule_id")?.asString ?: return
        val attendanceId = json.get("attendance_id")?.asString ?: return
        val subjectCode = json.get("subject_code")?.takeUnless { it.isJsonNull }?.asString
        val subjectName = json.get("subject_name")?.takeUnless { it.isJsonNull }?.asString
        val timestamp = json.get("timestamp")?.takeUnless { it.isJsonNull }?.asString

        val event: StudentAttendanceEvent = when (eventName) {
            "check_in" -> StudentAttendanceEvent.CheckIn(
                scheduleId = scheduleId,
                attendanceId = attendanceId,
                status = json.get("status")?.takeUnless { it.isJsonNull }?.asString ?: "present",
                checkInTime = json.get("check_in_time")?.takeUnless { it.isJsonNull }?.asString,
                subjectCode = subjectCode,
                subjectName = subjectName,
                timestamp = timestamp,
            )
            "early_leave" -> StudentAttendanceEvent.EarlyLeave(
                scheduleId = scheduleId,
                attendanceId = attendanceId,
                subjectCode = subjectCode,
                subjectName = subjectName,
                timestamp = timestamp,
            )
            "early_leave_return" -> StudentAttendanceEvent.EarlyLeaveReturn(
                scheduleId = scheduleId,
                attendanceId = attendanceId,
                restoredStatus = json.get("status")?.takeUnless { it.isJsonNull }?.asString ?: "present",
                returnedAt = json.get("check_in_time")?.takeUnless { it.isJsonNull }?.asString,
                subjectCode = subjectCode,
                subjectName = subjectName,
                timestamp = timestamp,
            )
            else -> {
                Log.d(TAG, "Unknown attendance_event.event=$eventName ignored")
                return
            }
        }
        _attendanceEvents.tryEmit(event)
        Log.d(TAG, "Attendance event: $eventName schedule=${scheduleId.take(8)}")
    }

    private fun scheduleReconnect() {
        val userId = userIdProvider.invoke()
        if (userId.isNullOrBlank()) return
        reconnectJob?.cancel()
        reconnectJob = scope.launch {
            delay(reconnectDelay)
            reconnectDelay = (reconnectDelay * 2).coerceAtMost(MAX_RECONNECT_DELAY)
            Log.i(TAG, "Reconnecting for user $userId...")
            doConnect()
        }
    }

    fun disconnect() {
        reconnectJob?.cancel()
        webSocket?.close(1000, "Closing")
        webSocket = null
        _isConnected.value = false
    }

    /**
     * Stop the client and wait for any in-flight reconnect coroutine to
     * finish. Call this on logout *before* clearing the TokenManager so the
     * reconnect job cannot race and read null credentials.
     */
    suspend fun disconnectAndAwait() {
        val job = reconnectJob
        reconnectJob = null
        job?.cancel()
        webSocket?.close(1000, "Closing")
        webSocket = null
        _isConnected.value = false
        job?.join()
    }

    fun destroy() {
        disconnect()
        scope.cancel()
    }
}
