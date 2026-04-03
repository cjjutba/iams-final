package com.iams.app.data.api

import android.util.Log
import com.iams.app.BuildConfig
import com.iams.app.data.model.NotificationEvent
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.OkHttpClient
import javax.inject.Inject
import javax.inject.Singleton

/**
 * App-scoped singleton managing the notification WebSocket lifecycle
 * and centralized unread count.
 *
 * Injected via Hilt. The WebSocket connects to `/api/v1/ws/alerts/{user_id}`
 * and emits real-time notification events that the UI observes for toasts.
 * The unread count is the single source of truth used by bottom-bar badges
 * and home screen indicators.
 */
@Singleton
class NotificationService @Inject constructor(
    private val tokenManager: TokenManager,
    private val okHttpClient: OkHttpClient,
) {
    companion object {
        private const val TAG = "NotificationService"
    }

    private var wsClient: NotificationWebSocketClient? = null

    private val _unreadCount = MutableStateFlow(0)
    val unreadCount: StateFlow<Int> = _unreadCount.asStateFlow()

    private val _isConnected = MutableStateFlow(false)
    val isConnected: StateFlow<Boolean> = _isConnected.asStateFlow()

    /**
     * The event stream from the WebSocket client.
     * Returns null if not connected — callers should check before collecting.
     */
    val events: SharedFlow<NotificationEvent>?
        get() = wsClient?.events

    /**
     * Create and start the notification WebSocket client.
     * Uses userId and accessToken from [TokenManager].
     */
    fun connect() {
        // Avoid duplicate connections
        if (wsClient != null) {
            Log.d(TAG, "Already connected, disconnecting old client first")
            wsClient?.disconnect()
        }

        val baseWsUrl = "ws://${BuildConfig.BACKEND_HOST}:${BuildConfig.BACKEND_PORT}/api/v1/ws"

        wsClient = NotificationWebSocketClient(
            baseUrl = baseWsUrl,
            client = okHttpClient,
            tokenProvider = { tokenManager.accessToken },
            userIdProvider = { tokenManager.userId },
        )
        wsClient?.connect()

        // Forward connection state
        // We collect this in the calling coroutine scope via the NavViewModel
        Log.i(TAG, "Notification WS client created and connecting")
    }

    /**
     * Close the WebSocket client and clean up.
     */
    fun disconnect() {
        wsClient?.destroy()
        wsClient = null
        _isConnected.value = false
        Log.i(TAG, "Notification WS client disconnected")
    }

    /**
     * Fetch the current unread count from the REST API and update the centralized state.
     */
    suspend fun fetchUnreadCount(apiService: ApiService) {
        try {
            val response = apiService.getUnreadCount()
            if (response.isSuccessful) {
                _unreadCount.value = response.body()?.unreadCount ?: 0
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to fetch unread count: ${e.message}")
        }
    }

    fun incrementUnreadCount() {
        _unreadCount.value = _unreadCount.value + 1
    }

    fun decrementUnreadCount() {
        _unreadCount.value = (_unreadCount.value - 1).coerceAtLeast(0)
    }

    fun setUnreadCount(count: Int) {
        _unreadCount.value = count.coerceAtLeast(0)
    }
}
