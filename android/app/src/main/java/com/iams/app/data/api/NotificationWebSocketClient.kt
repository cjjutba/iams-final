package com.iams.app.data.api

import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonParser
import com.iams.app.data.model.NotificationEvent
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
 * WebSocket client for real-time notification delivery.
 *
 * Connects to `/api/v1/ws/alerts/{user_id}?token={jwt}` and emits
 * [NotificationEvent] instances via a [SharedFlow] (each event processed once).
 *
 * Auto-reconnects with exponential backoff using coroutines.
 *
 * @param baseUrl        WebSocket base URL (e.g. ws://host:port/api/v1/ws)
 * @param client         Shared OkHttpClient instance (do NOT shut down in destroy)
 * @param tokenProvider  Lambda returning the current JWT access token, or null
 * @param userIdProvider Lambda returning the current user ID, or null
 */
class NotificationWebSocketClient(
    private val baseUrl: String,
    private val client: OkHttpClient,
    private val tokenProvider: () -> String?,
    private val userIdProvider: () -> String?,
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

    // Notification events — SharedFlow so each event is processed once (no replay)
    private val _events = MutableSharedFlow<NotificationEvent>(
        replay = 0,
        extraBufferCapacity = 20,
    )
    val events: SharedFlow<NotificationEvent> = _events.asSharedFlow()

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
                Log.i(TAG, "Connected to alerts for user $userId")
            }

            override fun onMessage(ws: WebSocket, text: String) {
                if (text == "pong") return
                try {
                    val json = JsonParser.parseString(text).asJsonObject
                    val type = json.get("type")?.asString
                    if (type == null) {
                        Log.w(TAG, "Received message without type field")
                        return
                    }

                    val event = gson.fromJson(text, NotificationEvent::class.java)
                    // Emit to SharedFlow — if buffer is full, drop oldest
                    _events.tryEmit(event)
                    Log.d(TAG, "Notification event: ${event.title}")
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to parse notification message: ${e.message}")
                }
            }

            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                _isConnected.value = false
                Log.i(TAG, "WebSocket closed: $reason")
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

    fun destroy() {
        disconnect()
        scope.cancel()
    }
}
