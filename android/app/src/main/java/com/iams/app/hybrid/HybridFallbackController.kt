package com.iams.app.hybrid

import android.util.Log
import com.iams.app.data.sync.TimeSyncClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicLong

/**
 * Operating mode of the hybrid detection pipeline.
 *
 * - [HYBRID]       — ML Kit emits face boxes AND backend WS is delivering identities.
 * - [BACKEND_ONLY] — ML Kit silent (>2s) or unavailable; the screen falls back to the legacy
 *                    backend-authoritative overlay (identities + boxes from the backend).
 * - [DEGRADED]     — Backend WS silent (>3s) but ML Kit still running; matcher is told to coast
 *                    on its last known bindings (MLKIT_ONLY/COASTING sources).
 * - [OFFLINE]      — Both ML Kit silent AND backend WS down; no overlay is drawn.
 */
enum class HybridMode { HYBRID, BACKEND_ONLY, DEGRADED, OFFLINE }

/**
 * Watches ML Kit callback cadence and backend WebSocket liveness, exposing a [HybridMode] state
 * flow that downstream UI uses to swap overlays. Drives [FaceIdentityMatcher.onBackendDisconnected]
 * / [FaceIdentityMatcher.onBackendReconnected] when the backend leg goes down/up so the matcher can
 * flip its tracks into COASTING mode without any extra glue in the consumer.
 *
 * Hard rules (see Session 09 plan):
 * - All callers report timestamps with [System.nanoTime] so the controller can compare staleness
 *   without locks. Timestamps are stored as [AtomicLong].
 * - The ticker runs on the injected [scope] (typically `viewModelScope`); cancelling that scope
 *   automatically tears down the controller.
 * - [reportMlkitUpdate] MUST be called on every ML Kit sink emission, even when the face list is
 *   empty (covered-camera case must NOT trigger BACKEND_ONLY). The sink lifecycle is owned by
 *   Session 02 — this controller does not restart it.
 * - The controller never tries to reconnect the WebSocket; it only reacts to liveness signals
 *   delivered by the WS client.
 */
class HybridFallbackController(
    private val matcher: FaceIdentityMatcher,
    @Suppress("unused") private val timeSync: TimeSyncClient,
    private val scope: CoroutineScope,
    private val config: Config = Config(),
) {

    /**
     * Tunables. Defaults match the Session 09 plan; tests inject a smaller [tickIntervalMs] to
     * exercise the transition matrix in real time without slowing the suite.
     */
    data class Config(
        val mlkitSilenceTimeoutMs: Long = 2_000L,
        val wsSilenceTimeoutMs: Long = 3_000L,
        val rttWarningMs: Long = 1_500L,
        val tickIntervalMs: Long = 500L,
    )

    private val _mode = MutableStateFlow(HybridMode.HYBRID)
    val mode: StateFlow<HybridMode> = _mode.asStateFlow()

    private val lastMlkitNs = AtomicLong(System.nanoTime())
    private val lastBackendNs = AtomicLong(System.nanoTime())

    private var tickerJob: Job? = null

    fun reportMlkitUpdate(nowNs: Long) {
        lastMlkitNs.set(nowNs)
    }

    fun reportBackendMessage(nowNs: Long) {
        lastBackendNs.set(nowNs)
    }

    /** Hard event: WS just connected — refresh the backend liveness clock immediately. */
    fun reportWsConnected() {
        lastBackendNs.set(System.nanoTime())
    }

    /** Hard event: WS just dropped — force the backend leg into the stale window on the next tick. */
    fun reportWsDisconnected() {
        lastBackendNs.set(0L)
    }

    fun start() {
        if (tickerJob?.isActive == true) return
        // Assume both legs healthy at start so we begin in HYBRID and only degrade when timestamps
        // genuinely fall behind. Without this, a slow first ML Kit emission could spuriously emit
        // BACKEND_ONLY before the sink wakes up.
        val now = System.nanoTime()
        lastMlkitNs.set(now)
        lastBackendNs.set(now)
        _mode.value = HybridMode.HYBRID
        tickerJob = scope.launch {
            while (isActive) {
                tickOnce()
                delay(config.tickIntervalMs)
            }
        }
    }

    fun stop() {
        tickerJob?.cancel()
        tickerJob = null
    }

    private fun tickOnce() {
        val now = System.nanoTime()
        val mlkitStaleNs = config.mlkitSilenceTimeoutMs * NANOS_PER_MS
        val wsStaleNs = config.wsSilenceTimeoutMs * NANOS_PER_MS
        val mlkitStale = (now - lastMlkitNs.get()) > mlkitStaleNs
        val wsStale = (now - lastBackendNs.get()) > wsStaleNs
        val newMode = computeMode(mlkitStale, wsStale)
        val current = _mode.value
        if (newMode != current) {
            applyTransition(current, newMode)
            _mode.value = newMode
        }
    }

    private fun applyTransition(from: HybridMode, to: HybridMode) {
        val wasDisconnected = from.isBackendDisconnected()
        val nowDisconnected = to.isBackendDisconnected()
        when {
            !wasDisconnected && nowDisconnected -> matcher.onBackendDisconnected()
            wasDisconnected && !nowDisconnected -> matcher.onBackendReconnected()
            else -> Unit // DEGRADED <-> OFFLINE: matcher already knows backend is down.
        }
        Log.i(TAG, "mode $from -> $to (rttMs=${timeSync.lastRttMs.value})")
    }

    companion object {
        private const val TAG = "HybridFallback"
        private const val NANOS_PER_MS = 1_000_000L

        /**
         * Pure transition matrix — exposed for unit testing without spinning up coroutines.
         * Mirrors the truth table in the Session 09 plan §4.
         */
        internal fun computeMode(mlkitStale: Boolean, wsStale: Boolean): HybridMode = when {
            mlkitStale && wsStale -> HybridMode.OFFLINE
            mlkitStale -> HybridMode.BACKEND_ONLY
            wsStale -> HybridMode.DEGRADED
            else -> HybridMode.HYBRID
        }

        private fun HybridMode.isBackendDisconnected(): Boolean =
            this == HybridMode.DEGRADED || this == HybridMode.OFFLINE
    }
}

// -----------------------------------------------------------------------------------------------
// Inline self-test — verifies the transition matrix without requiring JUnit on the classpath.
//
// The Session 09 plan asks for a "small inline test" of the matrix:
//     steady → stop mlkit → BACKEND_ONLY; resume → HYBRID;
//     cut WS → DEGRADED; cut both → OFFLINE.
//
// We exercise both layers:
//   1. The pure `computeMode` truth table (deterministic, no coroutines).
//   2. The integrated controller with a fast tick interval so the matcher disconnect/reconnect
//      side-effects are observed exactly once per entry into DEGRADED/OFFLINE.
//
// The test uses runBlocking + a real CoroutineScope; it does NOT need kotlinx-coroutines-test.
// Throws IllegalStateException on failure so callers (e.g. a debug menu hook or `main()` from
// `./gradlew :app:runFallbackSelfTest`-style invocation) get a clear stack.
// -----------------------------------------------------------------------------------------------
@Suppress("unused")
internal object HybridFallbackControllerSelfTest {

    fun run() {
        verifyComputeModeMatrix()
        verifyIntegratedTransitions()
    }

    private fun verifyComputeModeMatrix() {
        check(HybridFallbackController.computeMode(mlkitStale = false, wsStale = false) == HybridMode.HYBRID) {
            "expected HYBRID when both fresh"
        }
        check(HybridFallbackController.computeMode(mlkitStale = true, wsStale = false) == HybridMode.BACKEND_ONLY) {
            "expected BACKEND_ONLY when only ML Kit stale"
        }
        check(HybridFallbackController.computeMode(mlkitStale = false, wsStale = true) == HybridMode.DEGRADED) {
            "expected DEGRADED when only WS stale"
        }
        check(HybridFallbackController.computeMode(mlkitStale = true, wsStale = true) == HybridMode.OFFLINE) {
            "expected OFFLINE when both stale"
        }
    }

    private fun verifyIntegratedTransitions() = kotlinx.coroutines.runBlocking {
        val matcher = CountingMatcher()
        val scope = kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.Default + kotlinx.coroutines.SupervisorJob())
        val timeSync = NoOpTimeSync()
        // Tight thresholds + fast ticks so the test runs in <1s of wall clock.
        val config = HybridFallbackController.Config(
            mlkitSilenceTimeoutMs = 50L,
            wsSilenceTimeoutMs = 80L,
            tickIntervalMs = 10L,
        )
        val controller = HybridFallbackController(matcher, timeSync, scope, config)
        try {
            controller.start()

            // 1) Steady state — keep both legs alive past the timeouts.
            beat(controller, durationMs = 120L, intervalMs = 10L, mlkit = true, ws = true)
            check(controller.mode.value == HybridMode.HYBRID) {
                "steady state should be HYBRID, was ${controller.mode.value}"
            }

            // 2) Stop ML Kit (only WS continues) -> BACKEND_ONLY (matcher NOT notified).
            beat(controller, durationMs = 120L, intervalMs = 10L, mlkit = false, ws = true)
            check(controller.mode.value == HybridMode.BACKEND_ONLY) {
                "ML Kit silent should yield BACKEND_ONLY, was ${controller.mode.value}"
            }
            check(matcher.disconnectCount == 0) {
                "BACKEND_ONLY entry must not call onBackendDisconnected"
            }

            // 3) Resume ML Kit -> HYBRID.
            beat(controller, durationMs = 60L, intervalMs = 10L, mlkit = true, ws = true)
            check(controller.mode.value == HybridMode.HYBRID) {
                "resume should restore HYBRID, was ${controller.mode.value}"
            }

            // 4) Cut WS only (ML Kit still beating) -> DEGRADED, onBackendDisconnected fires once.
            controller.reportWsDisconnected()
            beat(controller, durationMs = 120L, intervalMs = 10L, mlkit = true, ws = false)
            check(controller.mode.value == HybridMode.DEGRADED) {
                "WS down should yield DEGRADED, was ${controller.mode.value}"
            }
            check(matcher.disconnectCount == 1) {
                "DEGRADED entry must call onBackendDisconnected exactly once, got ${matcher.disconnectCount}"
            }

            // 5) Cut ML Kit too -> OFFLINE. matcher already disconnected; no extra disconnect call.
            beat(controller, durationMs = 120L, intervalMs = 20L, mlkit = false, ws = false)
            check(controller.mode.value == HybridMode.OFFLINE) {
                "both stale should yield OFFLINE, was ${controller.mode.value}"
            }
            check(matcher.disconnectCount == 1) {
                "DEGRADED -> OFFLINE must NOT re-call onBackendDisconnected, got ${matcher.disconnectCount}"
            }

            // 6) Recover both -> HYBRID, onBackendReconnected fires exactly once.
            controller.reportWsConnected()
            beat(controller, durationMs = 60L, intervalMs = 10L, mlkit = true, ws = true)
            check(controller.mode.value == HybridMode.HYBRID) {
                "full recovery should yield HYBRID, was ${controller.mode.value}"
            }
            check(matcher.reconnectCount == 1) {
                "HYBRID re-entry must call onBackendReconnected exactly once, got ${matcher.reconnectCount}"
            }
        } finally {
            controller.stop()
            scope.cancel()
        }
    }

    private suspend fun beat(
        controller: HybridFallbackController,
        durationMs: Long,
        intervalMs: Long,
        mlkit: Boolean,
        ws: Boolean,
    ) {
        val deadline = System.currentTimeMillis() + durationMs
        while (System.currentTimeMillis() < deadline) {
            val now = System.nanoTime()
            if (mlkit) controller.reportMlkitUpdate(now)
            if (ws) controller.reportBackendMessage(now)
            kotlinx.coroutines.delay(intervalMs)
        }
    }

    private class CountingMatcher : FaceIdentityMatcher {
        @Volatile var disconnectCount: Int = 0
        @Volatile var reconnectCount: Int = 0
        override val tracks: StateFlow<List<HybridTrack>> =
            MutableStateFlow<List<HybridTrack>>(emptyList()).asStateFlow()
        override fun onMlKitUpdate(faces: List<com.iams.app.webrtc.MlKitFace>, frameTimestampNs: Long) = Unit
        override fun onBackendFrame(
            tracks: List<com.iams.app.data.model.TrackInfo>,
            serverTimeMs: Long?,
            receivedAtNs: Long,
        ) = Unit
        override fun onBackendDisconnected() { disconnectCount++ }
        override fun onBackendReconnected() { reconnectCount++ }
        override fun reset() = Unit
    }

    private class NoOpTimeSync : TimeSyncClient {
        override val skewMs: StateFlow<Long> = MutableStateFlow(0L).asStateFlow()
        override val lastRttMs: StateFlow<Long> = MutableStateFlow(-1L).asStateFlow()
        override fun start(baseUrl: String) = Unit
        override fun stop() = Unit
    }
}
