package com.iams.app.ui.debug

import com.iams.app.hybrid.HybridSource
import com.iams.app.hybrid.HybridTrack

/**
 * Rolling-window metrics collector for the hybrid live-feed HUD.
 *
 * Produces a [Snapshot] on demand from:
 * - ML Kit callback cadence (last 30 samples → FPS)
 * - Backend `frame_update` cadence + `frame_sequence` gap
 * - Matcher track list (bindings breakdown)
 * - Time-sync skew + RTT (supplied by caller)
 *
 * Thread safety: two dispatchers write to this instance (the ML Kit executor routes
 * through a ViewModel-scoped Dispatchers.Default coroutine, and the WebSocket parse
 * coroutine does likewise). All mutating methods and the snapshot read are guarded by
 * `synchronized(this)` — the critical sections are a few ns and never allocate past the
 * window bound.
 *
 * Not wired by this session. See handoff notes in
 * `docs/plans/2026-04-17-hybrid-detection/06-live-feed-integration.md` for the
 * ViewModel wiring snippet (Session 06 owner).
 */
class DiagnosticMetricsCollector {

    data class Snapshot(
        val mlkitFps: Float,
        val backendFps: Float,
        val skewMs: Long,
        val rttMs: Long,
        val bindingsCount: Int,
        val boundCount: Int,
        val coastingCount: Int,
        val mlkitOnlyCount: Int,
        val fallbackCount: Int,
        val lastSeqGap: Int,
    ) {
        companion object {
            val EMPTY = Snapshot(
                mlkitFps = 0f,
                backendFps = 0f,
                skewMs = 0L,
                rttMs = -1L,
                bindingsCount = 0,
                boundCount = 0,
                coastingCount = 0,
                mlkitOnlyCount = 0,
                fallbackCount = 0,
                lastSeqGap = 0,
            )
        }
    }

    private val mlkitTimes = ArrayDeque<Long>()
    private val backendTimes = ArrayDeque<Long>()
    private var lastSeq: Int? = null
    private var lastSeqGap: Int = 0
    private var lastSeqGapResetAtNs: Long = 0L

    fun recordMlkit(nowNs: Long) = synchronized(this) {
        push(mlkitTimes, nowNs)
    }

    fun recordBackend(nowNs: Long, sequence: Int?) = synchronized(this) {
        push(backendTimes, nowNs)
        if (sequence != null) {
            val prev = lastSeq
            if (prev != null) {
                val gap = sequence - (prev + 1)
                if (gap > lastSeqGap) {
                    lastSeqGap = gap
                    lastSeqGapResetAtNs = nowNs
                }
            }
            lastSeq = sequence
        }
    }

    fun snapshot(
        tracks: List<HybridTrack>,
        skewMs: Long,
        rttMs: Long,
        nowNs: Long,
    ): Snapshot = synchronized(this) {
        if (lastSeqGapResetAtNs != 0L && (nowNs - lastSeqGapResetAtNs) > SEQ_GAP_RESET_NS) {
            lastSeqGap = 0
        }
        return Snapshot(
            mlkitFps = fpsOf(mlkitTimes, nowNs),
            backendFps = fpsOf(backendTimes, nowNs),
            skewMs = skewMs,
            rttMs = rttMs,
            bindingsCount = tracks.count { it.backendTrackId != null },
            boundCount = tracks.count { it.source == HybridSource.BOUND },
            coastingCount = tracks.count { it.source == HybridSource.COASTING },
            mlkitOnlyCount = tracks.count { it.source == HybridSource.MLKIT_ONLY },
            fallbackCount = tracks.count { it.source == HybridSource.FALLBACK },
            lastSeqGap = lastSeqGap,
        )
    }

    fun reset() = synchronized(this) {
        mlkitTimes.clear()
        backendTimes.clear()
        lastSeq = null
        lastSeqGap = 0
        lastSeqGapResetAtNs = 0L
    }

    private fun push(q: ArrayDeque<Long>, now: Long) {
        q.addLast(now)
        while (q.size > WINDOW_SIZE) q.removeFirst()
    }

    private fun fpsOf(q: ArrayDeque<Long>, now: Long): Float {
        if (q.size < 2) return 0f
        val span = (now - q.first()).coerceAtLeast(1L)
        return (q.size - 1) * 1_000_000_000f / span
    }

    companion object {
        private const val WINDOW_SIZE = 30
        private const val SEQ_GAP_RESET_NS = 5_000_000_000L
    }
}
