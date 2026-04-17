# Session 08 — Diagnostic HUD

**Deliverable:** a debug-only overlay showing matcher metrics, clock skew, FPS, and binding stats. Toggle via long-press on an invisible corner or a settings flag.
**Blocks:** session 10 (tuning uses the HUD).
**Blocked by:** sessions 01, 03, 04 (reads their state).
**Est. effort:** 3 hours.

---

## 1. Scope

A Compose composable `HybridDiagnosticHud` that renders on top of the live feed (but below the action buttons) and displays:

- ML Kit FPS (from callback cadence).
- Backend FPS (from `frame_update.fps`).
- Clock skew ms (from TimeSyncClient).
- RTT ms (from TimeSyncClient).
- Active bindings count (from matcher).
- Sources breakdown (count of BOUND / COASTING / MLKIT_ONLY / FALLBACK).
- Frame sequence gaps (from backend `frame_sequence`).

Only visible in `BuildConfig.DEBUG` builds, or when a long-press gesture toggles it in release. Zero impact when hidden.

## 2. Files

| Path | New? |
|------|------|
| `android/app/src/main/java/com/iams/app/ui/debug/HybridDiagnosticHud.kt` | NEW |
| `android/app/src/main/java/com/iams/app/ui/debug/DiagnosticMetricsCollector.kt` | NEW |

## 3. Metrics collector

Pure class collecting rolling window statistics:

```kotlin
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
        val lastSeqGap: Int,       // max observed gap in frame_sequence in last 5 s
    )

    private val mlkitTimes = ArrayDeque<Long>()  // nanos of last 30 ml-kit updates
    private val backendTimes = ArrayDeque<Long>()
    private var lastSeq: Int? = null
    private var lastSeqGap: Int = 0
    private var lastSeqGapResetAtNs: Long = 0L

    fun recordMlkit(nowNs: Long) { push(mlkitTimes, nowNs) }
    fun recordBackend(nowNs: Long, sequence: Int?) {
        push(backendTimes, nowNs)
        if (sequence != null && lastSeq != null) {
            val gap = sequence - (lastSeq!! + 1)
            if (gap > lastSeqGap) { lastSeqGap = gap; lastSeqGapResetAtNs = nowNs }
        }
        if (sequence != null) lastSeq = sequence
    }

    fun snapshot(
        tracks: List<HybridTrack>,
        skewMs: Long,
        rttMs: Long,
        nowNs: Long,
    ): Snapshot {
        // Reset seq-gap every 5 s so transient gaps don't linger
        if ((nowNs - lastSeqGapResetAtNs) > 5_000_000_000L) lastSeqGap = 0
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

    private fun push(q: ArrayDeque<Long>, now: Long) {
        q.addLast(now); while (q.size > 30) q.removeFirst()
    }

    private fun fpsOf(q: ArrayDeque<Long>, now: Long): Float {
        if (q.size < 2) return 0f
        val span = (now - q.first()).coerceAtLeast(1L)
        return (q.size - 1) * 1_000_000_000f / span
    }
}
```

## 4. HUD composable

```kotlin
@Composable
fun HybridDiagnosticHud(
    snapshot: DiagnosticMetricsCollector.Snapshot,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.padding(8.dp)
            .background(Color.Black.copy(alpha = 0.6f), RoundedCornerShape(6.dp))
            .padding(horizontal = 8.dp, vertical = 4.dp),
    ) {
        metricRow("ML Kit FPS", "%.1f".format(snapshot.mlkitFps), alert = snapshot.mlkitFps < 10f)
        metricRow("Backend FPS", "%.1f".format(snapshot.backendFps), alert = snapshot.backendFps < 8f)
        metricRow("Clock skew", "${snapshot.skewMs} ms", alert = abs(snapshot.skewMs) > 1500L)
        metricRow("RTT", "${snapshot.rttMs} ms", alert = snapshot.rttMs > 500L)
        metricRow("Bound / Coast / MLKit / FB",
                   "${snapshot.boundCount}/${snapshot.coastingCount}/${snapshot.mlkitOnlyCount}/${snapshot.fallbackCount}")
        if (snapshot.lastSeqGap > 0) metricRow("Seq gap", "${snapshot.lastSeqGap}", alert = true)
    }
}

@Composable
private fun metricRow(label: String, value: String, alert: Boolean = false) {
    Row {
        Text("$label:", color = Color.White.copy(alpha = 0.7f), fontSize = 10.sp)
        Spacer(Modifier.width(4.dp))
        Text(value, color = if (alert) Color(0xFFFF5252) else Color.White, fontSize = 10.sp)
    }
}
```

## 5. ViewModel wiring (Session 06 will add)

In `FacultyLiveFeedViewModel`:

```kotlin
val metricsCollector = DiagnosticMetricsCollector()
val hudSnapshot: StateFlow<DiagnosticMetricsCollector.Snapshot> = ... /* emits at 2 Hz */

fun onMlKitFaces(faces: List<MlKitFace>) {
    metricsCollector.recordMlkit(System.nanoTime())
    // existing code
}

// When parsing frame_update:
metricsCollector.recordBackend(System.nanoTime(), frameSequence)
```

And a 2 Hz ticker coroutine that computes `metricsCollector.snapshot(tracks, skew, rtt, System.nanoTime())` and pushes to `hudSnapshot`.

**Note:** Session 06 is the only session that may modify the ViewModel. This session delivers the collector + HUD + a short doc section in Session 06's plan telling Session 06 exactly what to wire.

## 6. Visibility control

```kotlin
var hudVisible by remember { mutableStateOf(BuildConfig.DEBUG) }
Box(modifier = Modifier
    .fillMaxSize()
    .pointerInput(Unit) {
        detectTapGestures(onLongPress = { hudVisible = !hudVisible })
    }
) {
    // existing overlay content
    if (hudVisible) {
        HybridDiagnosticHud(snapshot = hudSnapshot, modifier = Modifier.align(Alignment.TopStart))
    }
}
```

Place behind the existing action buttons (use Compose `zIndex` if stacking issues arise).

## 7. Acceptance criteria

- [ ] HUD shows within ~500 ms of opening Live Feed in debug build.
- [ ] Long-press on the video area toggles visibility.
- [ ] FPS numbers match expectations (ML Kit ~15, backend ~20).
- [ ] Clock skew shows non-zero within 2 s (matches Session 04 polling).
- [ ] No perceptible frame rate drop when HUD is visible (target: < 5 % compose time).
- [ ] Alerts (red text) appear when thresholds exceeded — test by disabling Wi-Fi.
- [ ] HUD invisible in release build by default.

## 8. Anti-goals

- Do not log metrics to a file. This is on-screen only.
- Do not send metrics to a backend endpoint.
- Do not add a settings toggle screen — long-press is sufficient.
- Do not make the HUD theme-aware (always dark translucent).

## 9. Handoff notes

**For Session 06:** add the ViewModel wiring block from §5 (2-Hz ticker, `recordMlkit`/`recordBackend` calls).

**For Session 10:** HUD is the primary tool for tuning IoU thresholds — don't finalize thresholds without watching it.

## 10. Risks

- **Compose recomposition cost:** the 2 Hz snapshot emission should not over-recompose. Use `collectAsStateWithLifecycle` + derive `key1 = snapshot.boundCount` etc. if needed.
- **ArrayDeque mutation from two threads:** both `recordMlkit` and `recordBackend` run on `Dispatchers.Default` via ViewModel scope. Guard with a `synchronized(this)` block on the collector; it's only a few ns overhead.

## 11. Commit message template

```
hybrid(08): diagnostic HUD for live-feed matching

On-screen overlay showing ML Kit / backend FPS, clock skew, RTT,
bindings breakdown, and frame-sequence gaps. Long-press toggles
visibility; default on in debug, off in release.

Used by session 10 for threshold tuning.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## 12. Lessons

- Observability-first: the HUD is how you know the system is healthy without logcat.
- Red-thresholded metrics catch regressions faster than absolute numbers.
