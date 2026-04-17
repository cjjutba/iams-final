package com.iams.app.data.sync

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Singleton

interface TimeSyncClient {
    /** Current estimate of (server_epoch_ms - device_epoch_ms). 0 if not yet synced. */
    val skewMs: StateFlow<Long>

    /** Last measured round-trip ms. -1 if not yet measured. */
    val lastRttMs: StateFlow<Long>

    fun start(baseUrl: String)
    fun stop()
}

@Singleton
class DefaultTimeSyncClient @Inject constructor(
    private val okHttpClient: OkHttpClient,
) : TimeSyncClient {

    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private val _skewMs = MutableStateFlow(0L)
    override val skewMs: StateFlow<Long> = _skewMs.asStateFlow()

    private val _lastRttMs = MutableStateFlow(-1L)
    override val lastRttMs: StateFlow<Long> = _lastRttMs.asStateFlow()

    private var job: Job? = null
    private val samples = ArrayDeque<Long>()

    override fun start(baseUrl: String) {
        if (job != null) return
        job = scope.launch {
            while (isActive) {
                try {
                    pollOnce(baseUrl)
                } catch (_: Exception) {
                    // Network failures, JSON errors, etc. — skip this sample.
                }
                delay(POLL_INTERVAL_MS)
            }
        }
    }

    override fun stop() {
        job?.cancel()
        job = null
        samples.clear()
        _skewMs.value = 0L
        _lastRttMs.value = -1L
    }

    private suspend fun pollOnce(baseUrl: String) = withContext(Dispatchers.IO) {
        val url = "${baseUrl.trimEnd('/')}/api/v1/health/time"
        val t0 = System.currentTimeMillis()
        val body = okHttpClient.newCall(Request.Builder().url(url).build()).execute().use { resp ->
            if (!resp.isSuccessful) return@withContext
            resp.body?.string() ?: return@withContext
        }
        val t1 = System.currentTimeMillis()
        val rtt = t1 - t0
        if (rtt > MAX_RTT_MS) return@withContext

        val serverMs = JSONObject(body).optLong("server_time_ms", -1L)
        if (serverMs <= 0L) return@withContext

        val skew = (serverMs + rtt / 2) - t1

        samples.addLast(skew)
        while (samples.size > WINDOW_SIZE) samples.removeFirst()
        _skewMs.value = samples.sorted()[samples.size / 2]
        _lastRttMs.value = rtt
    }

    private companion object {
        const val POLL_INTERVAL_MS = 60_000L
        const val MAX_RTT_MS = 2_000L
        const val WINDOW_SIZE = 5
    }
}
