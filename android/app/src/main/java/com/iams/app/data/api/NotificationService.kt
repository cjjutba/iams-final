package com.iams.app.data.api

import android.util.Log
import com.iams.app.BuildConfig
import com.iams.app.data.model.NotificationEvent
import com.iams.app.data.model.RealtimeConnectionHealth
import com.iams.app.data.model.StudentAttendanceEvent
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import okhttp3.OkHttpClient
import java.time.LocalDate
import javax.inject.Inject
import javax.inject.Singleton

/**
 * App-scoped singleton owning the per-user WebSocket to `/ws/alerts/{user_id}`.
 *
 * Beyond toast notifications, this service now also carries real-time
 * attendance state changes (check_in / early_leave / early_leave_return)
 * for the logged-in student. Exactly one WS is held; dispatch happens by
 * envelope `type` inside [NotificationWebSocketClient].
 *
 * The class name stays `NotificationService` to preserve the 30+ existing
 * Hilt injection sites (faculty + student) while the responsibilities
 * widen to match what the student portal needs to go fully real-time.
 *
 * Exposes:
 *  - [events]: toast notifications (backwards compatible)
 *  - [attendanceEvents]: student-level attendance state-change stream
 *  - [unreadCount]: REST-synced unread notification count
 *  - [connectionHealth]: CONNECTED / RECONNECTING / OFFLINE for UI banners
 *  - [todayStatusByScheduleId]: map of `schedule_id -> status` for today,
 *    seeded from `/attendance/me` and live-patched on every event.
 */
@Singleton
class NotificationService @Inject constructor(
    private val tokenManager: TokenManager,
    private val okHttpClient: OkHttpClient,
    private val apiService: ApiService,
) {
    companion object {
        private const val TAG = "NotificationService"
        // Disconnect durations shorter than this are treated as transient —
        // no catch-up refresh fires. Tuned against the OkHttp backoff floor.
        private const val RECONNECT_GAP_REFRESH_MS = 10_000L
    }

    private var wsClient: NotificationWebSocketClient? = null
    private val syncScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var attendanceForwarder: Job? = null
    private var healthForwarder: Job? = null

    private val _unreadCount = MutableStateFlow(0)
    val unreadCount: StateFlow<Int> = _unreadCount.asStateFlow()

    private val _connectionHealth = MutableStateFlow(RealtimeConnectionHealth.OFFLINE)
    val connectionHealth: StateFlow<RealtimeConnectionHealth> = _connectionHealth.asStateFlow()

    private val _todayStatusByScheduleId = MutableStateFlow<Map<String, String>>(emptyMap())
    val todayStatusByScheduleId: StateFlow<Map<String, String>> =
        _todayStatusByScheduleId.asStateFlow()

    /**
     * Legacy `isConnected` flag some faculty screens still collect.
     * Kept as a boolean mirror of [connectionHealth].
     */
    private val _isConnected = MutableStateFlow(false)
    val isConnected: StateFlow<Boolean> = _isConnected.asStateFlow()

    // Re-emitter: public shared flow for attendance events that survives
    // WS client recreations. Views collect this, not the underlying client.
    private val _attendanceEvents = MutableSharedFlow<StudentAttendanceEvent>(
        replay = 0,
        extraBufferCapacity = 32,
    )
    val attendanceEvents: SharedFlow<StudentAttendanceEvent> = _attendanceEvents

    /**
     * Back-compat accessor used by existing notification screens.
     * Null when the client has not yet been constructed.
     */
    val events: SharedFlow<NotificationEvent>?
        get() = wsClient?.events

    fun connect() {
        if (wsClient != null) {
            Log.d(TAG, "Already connected, disconnecting old client first")
            wsClient?.disconnect()
        }

        val baseWsUrl = "ws://${BuildConfig.BACKEND_HOST}:${BuildConfig.BACKEND_PORT}/api/v1/ws"

        val client = NotificationWebSocketClient(
            baseUrl = baseWsUrl,
            client = okHttpClient,
            tokenProvider = { tokenManager.accessToken },
            userIdProvider = { tokenManager.userId },
            onConnected = { gapMillis ->
                syncScope.launch {
                    fetchUnreadCount(apiService)
                    // Seed today's status map (every reconnect is cheap —
                    // one small REST call). Also serves as the catch-up
                    // refresh for reconnect gaps that outlast the grace
                    // window: any state changes we missed over WS are
                    // reconciled through the snapshot.
                    refreshTodaySnapshot(emitSnapshotEvent = gapMillis >= RECONNECT_GAP_REFRESH_MS)
                }
            },
        )
        wsClient = client

        // Forward the WS client's raw attendance events into our
        // long-lived SharedFlow. Keep the today-status map in sync.
        attendanceForwarder?.cancel()
        attendanceForwarder = syncScope.launch {
            client.attendanceEvents.collectLatest { event ->
                applyAttendanceEventToMap(event)
                _attendanceEvents.tryEmit(event)
            }
        }

        // Mirror the WS connection state into our StateFlows.
        healthForwarder?.cancel()
        _connectionHealth.value = RealtimeConnectionHealth.RECONNECTING
        healthForwarder = syncScope.launch {
            client.isConnected.collectLatest { connected ->
                _isConnected.value = connected
                _connectionHealth.value = if (connected) {
                    RealtimeConnectionHealth.CONNECTED
                } else {
                    RealtimeConnectionHealth.RECONNECTING
                }
            }
        }

        client.connect()
        Log.i(TAG, "Notification WS client created and connecting")
    }

    /**
     * Close the WebSocket client and clean up. Non-blocking — prefer
     * [disconnectAndAwait] on logout to avoid a token-clear race.
     */
    fun disconnect() {
        wsClient?.destroy()
        wsClient = null
        _isConnected.value = false
        _connectionHealth.value = RealtimeConnectionHealth.OFFLINE
        attendanceForwarder?.cancel()
        healthForwarder?.cancel()
        _todayStatusByScheduleId.value = emptyMap()
        Log.i(TAG, "Notification WS client disconnected")
    }

    /**
     * Stop the WebSocket and await any in-flight reconnect coroutine
     * before returning. Call this on logout *before* clearing tokens so
     * the reconnect job cannot race and read a null `userId` / `token`.
     */
    suspend fun disconnectAndAwait() {
        wsClient?.disconnectAndAwait()
        wsClient?.destroy()
        wsClient = null
        _isConnected.value = false
        _connectionHealth.value = RealtimeConnectionHealth.OFFLINE
        attendanceForwarder?.cancelAndJoin()
        healthForwarder?.cancelAndJoin()
        _todayStatusByScheduleId.value = emptyMap()
        Log.i(TAG, "Notification WS client disconnected (awaited)")
    }

    /** Fetch the current unread count from REST and update [unreadCount]. */
    suspend fun fetchUnreadCount(apiService: ApiService = this.apiService) {
        try {
            val response = apiService.getUnreadCount()
            if (response.isSuccessful) {
                _unreadCount.value = response.body()?.unreadCount ?: 0
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to fetch unread count: ${e.message}")
        }
    }

    /**
     * Seed/refresh [todayStatusByScheduleId] from today's attendance. When
     * [emitSnapshotEvent] is true, also publish a
     * [StudentAttendanceEvent.SnapshotUpdate] so ViewModels showing
     * today-scoped lists can reconcile their in-memory state against the
     * server truth.
     */
    suspend fun refreshTodaySnapshot(emitSnapshotEvent: Boolean = false) {
        try {
            val today = LocalDate.now().toString()
            val response = apiService.getMyAttendance(today, today)
            if (!response.isSuccessful) return
            val records = response.body().orEmpty()
            _todayStatusByScheduleId.value = records
                .associate { (it.scheduleId ?: "") to it.status }
                .filterKeys { it.isNotBlank() }
            if (emitSnapshotEvent) {
                _attendanceEvents.tryEmit(StudentAttendanceEvent.SnapshotUpdate(records))
            }
        } catch (e: Exception) {
            Log.w(TAG, "refreshTodaySnapshot failed: ${e.message}")
        }
    }

    private fun applyAttendanceEventToMap(event: StudentAttendanceEvent) {
        val current = _todayStatusByScheduleId.value.toMutableMap()
        when (event) {
            is StudentAttendanceEvent.CheckIn -> current[event.scheduleId] = event.status
            is StudentAttendanceEvent.EarlyLeave -> current[event.scheduleId] = "early_leave"
            is StudentAttendanceEvent.EarlyLeaveReturn ->
                current[event.scheduleId] = event.restoredStatus
            is StudentAttendanceEvent.SnapshotUpdate -> {
                // Snapshot replaces the whole map wholesale.
                _todayStatusByScheduleId.value = event.records
                    .associate { (it.scheduleId ?: "") to it.status }
                    .filterKeys { it.isNotBlank() }
                return
            }
        }
        _todayStatusByScheduleId.value = current
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
