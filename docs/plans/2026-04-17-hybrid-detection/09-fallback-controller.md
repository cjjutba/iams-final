# Session 09 — Hybrid Fallback Controller

**Deliverable:** a coordinator that decides, based on ML Kit and WebSocket health, whether to stay in hybrid mode, degrade to backend-only, or hide boxes entirely. Drives `matcher.onBackendDisconnected/Reconnected` and exposes a public status flow the overlay/HUD can react to.
**Blocks:** session 06, 10.
**Blocked by:** sessions 01, 04 (reads matcher + timeSync).
**Est. effort:** 2 hours.

---

## 1. Scope

Today there's an implicit assumption that if the WS is up and ML Kit is running, hybrid works. Reality is messier: ML Kit can fail (permissions denied, device doesn't have Play Services), WS can be flaky, RTT can balloon. This session adds one class that watches these signals and flips matcher state appropriately.

## 2. Files

| Path | New? |
|------|------|
| `android/app/src/main/java/com/iams/app/hybrid/HybridFallbackController.kt` | NEW |

## 3. Inputs / outputs

```kotlin
enum class HybridMode {
    HYBRID,         // ML Kit + backend both healthy — normal mode
    BACKEND_ONLY,   // ML Kit silent > 2s or not started — fall back to legacy overlay
    DEGRADED,       // WS down > 3s but ML Kit still running — show MLKIT_ONLY/COASTING
    OFFLINE,        // Both ML Kit silent AND WS down — hide boxes
}

class HybridFallbackController(
    private val matcher: FaceIdentityMatcher,
    private val timeSync: TimeSyncClient,
    private val scope: CoroutineScope,
    private val config: Config = Config(),
) {
    data class Config(
        val mlkitSilenceTimeoutMs: Long = 2_000L,
        val wsSilenceTimeoutMs: Long = 3_000L,
        val rttWarningMs: Long = 1_500L,
    )

    private val _mode = MutableStateFlow(HybridMode.HYBRID)
    val mode: StateFlow<HybridMode> = _mode.asStateFlow()

    fun reportMlkitUpdate(nowNs: Long)
    fun reportBackendMessage(nowNs: Long)
    fun reportWsConnected()
    fun reportWsDisconnected()
    fun start()
    fun stop()
}
```

## 4. Implementation

Keep two volatile `AtomicLong`s: `lastMlkitNs`, `lastBackendNs`. `reportMlkitUpdate` and `reportBackendMessage` set them (lock-free).

On `start()`, launch a coroutine that ticks every 500 ms:

```kotlin
scope.launch {
    while (isActive) {
        val now = System.nanoTime()
        val mlkitStale = (now - lastMlkitNs.get()) > config.mlkitSilenceTimeoutMs * 1_000_000
        val wsStale = (now - lastBackendNs.get()) > config.wsSilenceTimeoutMs * 1_000_000
        val newMode = when {
            mlkitStale && wsStale -> HybridMode.OFFLINE
            mlkitStale            -> HybridMode.BACKEND_ONLY
            wsStale               -> HybridMode.DEGRADED
            else                  -> HybridMode.HYBRID
        }
        if (newMode != _mode.value) {
            handleTransition(_mode.value, newMode)
            _mode.value = newMode
        }
        delay(500)
    }
}
```

`handleTransition`:
- Entering `DEGRADED` or `OFFLINE`: call `matcher.onBackendDisconnected()`.
- Leaving `DEGRADED`/`OFFLINE` back to `HYBRID`: call `matcher.onBackendReconnected()`.
- No matcher call for `BACKEND_ONLY` transitions (the screen swaps to legacy overlay — Session 06 handles that based on `mode`).

`reportWsConnected` and `reportWsDisconnected` are hard events — they immediately force `lastBackendNs` to now or to 0 respectively.

## 5. How Session 06 consumes it

```kotlin
val fallback = HybridFallbackController(matcher, timeSync, viewModelScope)
fallback.start()

// In WS message handler:
fallback.reportBackendMessage(System.nanoTime())
// In ML Kit callback:
fallback.reportMlkitUpdate(System.nanoTime())
// In WS connect / disconnect listeners:
fallback.reportWsConnected() / .reportWsDisconnected()

// Expose flow:
val mode: StateFlow<HybridMode> = fallback.mode
```

And in `FacultyLiveFeedScreen`:

```kotlin
val mode by viewModel.mode.collectAsStateWithLifecycle()
when (mode) {
    HybridMode.HYBRID, HybridMode.DEGRADED -> HybridTrackOverlay(hybridTracks, ...)
    HybridMode.BACKEND_ONLY -> InterpolatedTrackOverlay(tracks, ...)
    HybridMode.OFFLINE -> Unit   // no overlay
}
```

(Session 06 implements this; this session only delivers the controller.)

## 6. Acceptance criteria

- [ ] Controller compiles.
- [ ] Under steady state (both sides healthy) — `mode == HYBRID`.
- [ ] Stopping ML Kit callbacks for > 2 s — `mode == BACKEND_ONLY`.
- [ ] Cutting WS for > 3 s (but ML Kit still running) — `mode == DEGRADED`.
- [ ] Cutting both — `mode == OFFLINE`.
- [ ] Transition back to HYBRID is instant (next tick) once both recover.
- [ ] `matcher.onBackendDisconnected()` called exactly once per `DEGRADED`/`OFFLINE` entry.
- [ ] Small unit test (can live in this session's test file) verifies the transition matrix.

## 7. Anti-goals

- Do not make the controller restart the ML Kit sink (Session 02 owns lifecycle).
- Do not try to reconnect the WebSocket from here.
- Do not log verbose state on every tick (log only on transitions).
- Do not add a circuit breaker — too clever; not needed.

## 8. Handoff notes

**For Session 06:** spec above in §5 lines out exactly what to wire.

**For Session 10:** the test plan must cover all four modes. Use airplane mode + permission revocation to force each transition.

## 9. Risks

- **False OFFLINE:** if the user covers the camera, ML Kit emits no faces but the sink is still alive. That should NOT trigger BACKEND_ONLY. Solution: `reportMlkitUpdate` runs on every sink emission regardless of face count (Session 06 wires this — document it in the handoff).
- **Coroutine leak:** `scope` is the ViewModel scope — cancels automatically on `onCleared`.

## 10. Commit message template

```
hybrid(09): HybridFallbackController for ML Kit/WS health transitions

Watches ML Kit callback cadence and backend WebSocket liveness, emits a
HybridMode StateFlow (HYBRID / BACKEND_ONLY / DEGRADED / OFFLINE) that
Session 06 uses to swap overlays and drive matcher state.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## 11. Lessons

- Explicit mode enum beats booleans-in-booleans. Four states name themselves.
- Tick-based state machine is simpler than event-driven when all transitions are time-based.
