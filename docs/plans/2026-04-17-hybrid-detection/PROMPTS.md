# Claude Code Session Prompts — Hybrid Detection Rollout

Paste one block per Claude Code session. Each prompt is self-contained: it tells the session exactly what to read, what to build, what not to touch, and how to commit.

**Shared assumptions for every session:**

- Repo: `/Users/cjjutba/Projects/iams`, branch `feat/architecture-redesign`.
- Master plan: [docs/plans/2026-04-17-hybrid-detection/00-master-plan.md](00-master-plan.md).
- You must read the master plan §5 (shared contracts) before typing code. Those signatures are frozen — do not redefine, rename, or "improve" them.
- One PR per session. Commit message template is in each session plan's final section.
- Do not deploy to the VPS. Local Docker only (see `CLAUDE.md` project rules).

---

## SESSION 01 — FaceIdentityMatcher Engine

```
You are implementing Session 01 of the IAMS hybrid detection rollout.

Repo: /Users/cjjutba/Projects/iams
Branch: feat/architecture-redesign (already checked out)

REQUIRED READING (in this order):
1. docs/plans/2026-04-17-hybrid-detection/00-master-plan.md  (whole file; §5 especially)
2. docs/plans/2026-04-17-hybrid-detection/01-matcher-engine.md  (your session)

MISSION
Implement the pure-Kotlin matching engine that binds ML Kit face IDs to backend track identities. Three new files under `android/app/src/main/java/com/iams/app/hybrid/`:
- HybridTypes.kt  (data classes + MatcherConfig + enum — verbatim from master §5.1)
- IouMath.kt      (two iou() helpers)
- FaceIdentityMatcher.kt  (interface + DefaultFaceIdentityMatcher implementation)

HARD RULES
- Import `com.iams.app.webrtc.MlKitFace` and `com.iams.app.data.model.TrackInfo`; DO NOT redefine them.
- No Android framework imports in these three files. Pure JVM Kotlin.
- No `Dispatchers.*`, no logger, no side effects beyond StateFlow emission. Caller owns threading.
- Use the injected `clock: () -> Long` parameter; default `{ System.nanoTime() }`. No calls to `System.nanoTime()` inside the matcher body.
- Greedy IoU assignment (sort descending, accept if both sides unassigned and iou >= iouBindThreshold). Not Hungarian.
- Keep bindings keyed by `mlkitFaceId` (Int), NOT by geometric centroid.

DO NOT
- Do not write unit tests (Session 07 owns them).
- Do not touch MlKitFrameSink.kt, InterpolatedTrackOverlay.kt, or any other existing file.
- Do not add a logger.
- Do not implement clock sync.

ACCEPTANCE
- `./gradlew :app:compileDebugKotlin` passes (no warnings).
- `HybridTrack.equals` handles `FloatArray` correctly (Compose diffs cleanly).
- `reset()` returns matcher to fresh-instance state.
- Public surface matches master §5.1 + §5.2 verbatim.

WHEN DONE
- Create commit with the message template from section 9 of 01-matcher-engine.md.
- Report: files created, loc added, any deviations from the plan (ideally zero).
```

---

## SESSION 02 — Wire MlKitFrameSink into NativeWebRtcVideoPlayer

```
You are implementing Session 02 of the IAMS hybrid detection rollout.

Repo: /Users/cjjutba/Projects/iams
Branch: feat/architecture-redesign

REQUIRED READING:
1. docs/plans/2026-04-17-hybrid-detection/00-master-plan.md
2. docs/plans/2026-04-17-hybrid-detection/02-mlkit-sink-wiring.md
3. android/app/src/main/java/com/iams/app/webrtc/MlKitFrameSink.kt  (fully implemented; read so you know its API)

MISSION
Modify `android/app/src/main/java/com/iams/app/ui/components/NativeWebRtcVideoPlayer.kt` to attach `MlKitFrameSink` as a second VideoSink alongside the existing `SurfaceViewRenderer`, expose its `faces` + `frameSize` StateFlows via callback parameters, and close it on dispose.

SIGNATURE (exact):
@Composable
fun NativeWebRtcVideoPlayer(
    whepUrl: String,
    modifier: Modifier = Modifier,
    onError: (String) -> Unit = {},
    onVideoReady: () -> Unit = {},
    onMlKitFacesUpdate: (List<MlKitFace>) -> Unit = {},
    onMlKitFrameSize: (Int, Int) -> Unit = { _, _ -> },
    enableMlKit: Boolean = true,
)

HARD RULES
- Only modify NativeWebRtcVideoPlayer.kt. No other file.
- Default parameter values keep every existing call site working untouched.
- Close `MlKitFrameSink` BEFORE releasing `SurfaceViewRenderer` on dispose.
- Two separate `LaunchedEffect`s for the two StateFlow collections so one stalling doesn't block the other.
- `enableMlKit = false` → do not allocate the sink; no callbacks fired; zero overhead.

DO NOT
- Do not modify MlKitFrameSink.kt.
- Do not touch overlay code.
- Do not call any matcher here — this composable just emits raw ML Kit data.
- Do not log outside existing patterns.

ACCEPTANCE
- Build passes: `./gradlew assembleDebug`.
- When running live, logcat tag "MlKitFrameSink" shows frames being processed.
- `enableMlKit = false` path preserves the legacy render exactly.
- `DisposableEffect` cleans up both sinks.

WHEN DONE
- Commit per section 9 of 02-mlkit-sink-wiring.md.
- Confirm no existing call sites were broken.
```

---

## SESSION 03 — HybridTrackOverlay

```
You are implementing Session 03 of the IAMS hybrid detection rollout.

Repo: /Users/cjjutba/Projects/iams
Branch: feat/architecture-redesign

PREREQUISITE
Session 01 must be merged before this can compile. If the package `com.iams.app.hybrid` does not exist in the current working tree, either (a) pull the latest or (b) rebase on top of Session 01's branch before continuing.

REQUIRED READING:
1. docs/plans/2026-04-17-hybrid-detection/00-master-plan.md
2. docs/plans/2026-04-17-hybrid-detection/03-hybrid-track-overlay.md
3. android/app/src/main/java/com/iams/app/ui/components/InterpolatedTrackOverlay.kt  (styling reference)

MISSION
Create `android/app/src/main/java/com/iams/app/ui/components/HybridTrackOverlay.kt` — a Compose composable that renders ML Kit-positioned boxes with matcher-supplied identities at 30fps.

SIGNATURE
@Composable
fun HybridTrackOverlay(
    tracks: List<HybridTrack>,
    modifier: Modifier = Modifier,
    videoFrameWidth: Int = 0,
    videoFrameHeight: Int = 0,
    isVideoReady: Boolean = true,
    showCoasting: Boolean = true,
)

HARD RULES
- No snap interpolation. ML Kit delivers 30fps positions already; draw `track.bbox` directly.
- Aspect-fit / crop-offset math: copy-paste from InterpolatedTrackOverlay lines 182-202.
- Fade in 150ms, fade out 300ms. Match InterpolatedTrackOverlay behaviour.
- Source-to-color mapping is fixed:
    BOUND      = Color(0xFF4CAF50)   green
    COASTING   = Color(0xFF8BC34A)   dimmed green
    MLKIT_ONLY = Color(0xFFFF9800)   orange
    FALLBACK   = Color(0xFF2196F3)   blue
- Suppress MLKIT_ONLY tracks younger than 800ms (avoid flashing transient detections).
- Reuse the `drawNameLabel` helper from InterpolatedTrackOverlay verbatim.

DO NOT
- Do not read the matcher directly — the overlay takes its input via parameter.
- Do not modify InterpolatedTrackOverlay.
- Do not add interpolation.
- Do not manage matcher lifecycle.

ACCEPTANCE
- Build passes.
- `@Preview` composable with 3 synthetic HybridTracks renders correctly.
- `showCoasting = false` hides COASTING boxes.
- Labels truncate with ellipsis on overflow.
- `renderStates` map pruned when a faceId is absent > 500ms (no leak).

WHEN DONE
- Commit per section 8 of 03-hybrid-track-overlay.md.
```

---

## SESSION 04 — TimeSyncClient

```
You are implementing Session 04 of the IAMS hybrid detection rollout.

Repo: /Users/cjjutba/Projects/iams
Branch: feat/architecture-redesign

REQUIRED READING:
1. docs/plans/2026-04-17-hybrid-detection/00-master-plan.md  (especially §5.4)
2. docs/plans/2026-04-17-hybrid-detection/04-time-sync-utility.md
3. android/app/src/main/java/com/iams/app/di/NetworkModule.kt  (find the existing OkHttpClient to reuse)

MISSION
Implement a lightweight HTTP-based clock-skew estimator using Cristian's algorithm. Two new files:
- android/app/src/main/java/com/iams/app/data/sync/TimeSyncClient.kt
- android/app/src/main/java/com/iams/app/di/TimeSyncModule.kt

INTERFACE (frozen — master §5.4):
interface TimeSyncClient {
    val skewMs: StateFlow<Long>
    val lastRttMs: StateFlow<Long>
    fun start(baseUrl: String)
    fun stop()
}

ALGORITHM
- Poll GET /api/v1/health/time every 60s.
- For each sample: compute `skew = server_time_ms + rtt/2 - t1`.
- Discard samples where rtt > 2000ms.
- Keep a rolling window of 5 samples; publish the median as skewMs.

HARD RULES
- Reuse the existing OkHttpClient from the app's NetworkModule (Hilt @Inject).
- Use `org.json.JSONObject` to parse — do not couple to Moshi/Gson.
- `start()` is idempotent (second call is a no-op).
- `stop()` cancels the coroutine and resets flows to 0 / -1.
- No NTP / SNTP libraries.

DO NOT
- Do not poll more often than every 60s.
- Do not block the main thread.
- Do not expose the internal samples buffer.
- Do not implement the /health/time endpoint — Session 05 owns it.
- Do not wire this into the ViewModel — Session 06 owns it.

ACCEPTANCE
- Build passes.
- When backend is up, `skewMs` emits a non-zero value within 2s.
- When backend is down, `skewMs` stays 0 and `lastRttMs` stays -1.
- `samples` capped at 5 (no growth).

WHEN DONE
- Commit per section 10 of 04-time-sync-utility.md.
- Note: integration verification happens only after Session 05 ships the endpoint.
```

---

## SESSION 05 — Backend Protocol Additions

```
You are implementing Session 05 of the IAMS hybrid detection rollout.

Repo: /Users/cjjutba/Projects/iams
Branch: feat/architecture-redesign

REQUIRED READING:
1. docs/plans/2026-04-17-hybrid-detection/00-master-plan.md  (especially §5.3)
2. docs/plans/2026-04-17-hybrid-detection/05-backend-protocol-additions.md
3. backend/app/services/realtime_pipeline.py  (lines 278-309 for context)

MISSION
Two additive backend changes:
1. Add `server_time_ms` (UTC epoch ms) and `frame_sequence` (monotonic int) to every `frame_update` WS broadcast.
2. Add `GET /api/v1/health/time` returning `{"server_time_ms": <long>}`.

FILES
- MODIFY: backend/app/services/realtime_pipeline.py
- MODIFY or CREATE: backend/app/routers/health.py  (check if it exists; extend or create)
- NEW: backend/tests/test_websocket_protocol.py  (or extend existing tests)
- MODIFY (only if health.py is new): backend/app/main.py  (include the router)

HARD RULES
- Backwards compatible additions only. No protocol version bump.
- Initialise `self._frame_sequence = 0` in `SessionPipeline.__init__`. Increment at the top of `_broadcast_frame_update`.
- `server_time_ms = int(time.time() * 1000)` — UTC epoch ms.
- `/api/v1/health/time` is unauthenticated (trivial public endpoint).
- Do not touch `_broadcast_attendance_summary`, `_broadcast_stream_status`, `_handle_event`.

TESTING
Run in the container:
    docker compose exec api-gateway python -m pytest tests/test_websocket_protocol.py -q

Smoke test:
    curl http://localhost:8000/api/v1/health/time
    # expect {"server_time_ms": <13-digit int>}

DO NOT
- Do not change the pipeline's processing cadence.
- Do not rename existing fields.
- Do not add CORS or auth to /health/time.
- Do not bump any version numbers.

ACCEPTANCE
- Tests green.
- curl returns correct shape within ±5s of system clock.
- Live browser WS session shows `server_time_ms` + `frame_sequence` on every frame_update.
- `frame_sequence` strictly increasing within a session.

WHEN DONE
- Commit per section 8 of 05-backend-protocol-additions.md.
```

---

## SESSION 06 — FacultyLiveFeedScreen Integration

```
You are implementing Session 06 of the IAMS hybrid detection rollout.

Repo: /Users/cjjutba/Projects/iams
Branch: feat/architecture-redesign

PREREQUISITES (all must be merged first)
- Session 01 (matcher) — provides com.iams.app.hybrid.*
- Session 02 (sink wiring) — provides the new callback parameters on NativeWebRtcVideoPlayer
- Session 03 (overlay) — provides HybridTrackOverlay
- Session 04 (time-sync) — provides TimeSyncClient
- Session 05 (backend) — provides `server_time_ms` on WS payload
(Sessions 08 and 09 can still be in-flight; wire them opportunistically if present, skip cleanly if absent.)

REQUIRED READING:
1. docs/plans/2026-04-17-hybrid-detection/00-master-plan.md  (whole §5)
2. docs/plans/2026-04-17-hybrid-detection/06-live-feed-integration.md
3. docs/plans/2026-04-17-hybrid-detection/08-diagnostic-hud.md  (§5 — HUD wiring snippets)
4. docs/plans/2026-04-17-hybrid-detection/09-fallback-controller.md  (§5 — controller wiring snippets)

MISSION
Glue every merged component into the live-feed screen behind `BuildConfig.HYBRID_DETECTION_ENABLED`.

FILES TO MODIFY
- android/app/build.gradle.kts  (add `buildConfigField("boolean", "HYBRID_DETECTION_ENABLED", "true")`)
- android/app/src/main/java/com/iams/app/ui/faculty/FacultyLiveFeedViewModel.kt
- android/app/src/main/java/com/iams/app/ui/faculty/FacultyLiveFeedScreen.kt
- NEW: android/app/src/main/java/com/iams/app/di/HybridModule.kt  (Hilt @Binds for matcher)

HARD RULES
- Matcher calls MUST run on a single-threaded dispatcher. Use `Dispatchers.Default.limitedParallelism(1)` stored as a ViewModel field.
- Matcher is `@ViewModelScoped`, NOT `@Singleton`.
- BuildConfig flag defaults `true`; both code paths (legacy + hybrid) must compile and work.
- Parse `server_time_ms` as nullable Long from the WS payload; pass to matcher.onBackendFrame.
- Call `matcher.reset()` AND `timeSync.stop()` in `onCleared()`.
- If Session 09 (HybridFallbackController) is available, wire it; otherwise skip cleanly.
- If Session 08 (HUD) is available, add a 2Hz ticker coroutine as specified; otherwise skip.

OVERLAY SWITCH
In FacultyLiveFeedScreen.kt around line 413, replace:
    InterpolatedTrackOverlay(tracks = tracks, ...)
with:
    if (BuildConfig.HYBRID_DETECTION_ENABLED) {
        HybridTrackOverlay(tracks = hybridTracks, ...)
    } else {
        InterpolatedTrackOverlay(tracks = tracks, ...)
    }

DO NOT
- Do not modify the matcher, sink, overlay, time-sync, or fallback implementations.
- Do not change WS message types.
- Do not touch camera permissions logic.
- Do not deploy anywhere.

ACCEPTANCE
- Build passes.
- With flag = true: boxes smooth @30fps, names correct, yellow/green color semantics observed.
- With flag = false: identical to pre-change behaviour (regression check).
- Airplane-mode toggle: matcher reset on disconnect, re-binds on reconnect.
- Heap flat over a 10-min session (profile in Android Studio).

WHEN DONE
- Commit per section 8 of 06-live-feed-integration.md.
```

---

## SESSION 07 — Matcher Unit Tests

```
You are implementing Session 07 of the IAMS hybrid detection rollout.

Repo: /Users/cjjutba/Projects/iams
Branch: feat/architecture-redesign

PREREQUISITE
Session 01 must be merged (provides the types you're testing).

REQUIRED READING:
1. docs/plans/2026-04-17-hybrid-detection/00-master-plan.md  (§5)
2. docs/plans/2026-04-17-hybrid-detection/01-matcher-engine.md  (the code under test)
3. docs/plans/2026-04-17-hybrid-detection/07-matcher-unit-tests.md  (your session)

MISSION
Write ≥ 25 JUnit tests covering FaceIdentityMatcher and IouMath. Target ≥ 95% line coverage on `com.iams.app.hybrid`.

FILES
- NEW: android/app/src/test/java/com/iams/app/hybrid/FaceIdentityMatcherTest.kt
- NEW: android/app/src/test/java/com/iams/app/hybrid/IouMathTest.kt
- NEW: android/app/src/test/java/com/iams/app/hybrid/MatcherFixtures.kt  (builders + FakeClock)

TEST COVERAGE (as listed in 07-matcher-unit-tests.md §5)
- Category A: IoU math (5 tests)
- Category B: Basic matching (8 tests)
- Category C: Sticky release (6 tests)
- Category D: Identity-swap prevention (3 tests)
- Category E: Connectivity transitions (3 tests)
- Category F: Emit diff (2 tests)

DEPS (add to app/build.gradle.kts dependencies{} if missing)
testImplementation("junit:junit:4.13.2")
testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.0")
testImplementation("com.google.truth:truth:1.4.2")

HARD RULES
- No Robolectric. No Compose testing. No instrumentation.
- Use the injected `clock: () -> Long` via a `FakeClock` helper — never real time.
- Assert `FloatArray` content element-wise or with `usingTolerance`.
- All tests synchronous; do not use `runTest` / `delay` unless strictly needed.

DO NOT
- Do not modify matcher source to "make it testable" — use injection.
- Do not use reflection.
- Do not add flaky tests (run 5× locally before declaring done).

ACCEPTANCE
- `./gradlew :app:testDebugUnitTest` passes.
- `./gradlew :app:jacocoTestReport` shows ≥ 95% line coverage on `com.iams.app.hybrid`.
- All tests finish in < 2 s total.

WHEN DONE
- Commit per section 10 of 07-matcher-unit-tests.md.
```

---

## SESSION 08 — Diagnostic HUD

```
You are implementing Session 08 of the IAMS hybrid detection rollout.

Repo: /Users/cjjutba/Projects/iams
Branch: feat/architecture-redesign

PREREQUISITE (loose)
Works best once Sessions 01 and 04 are merged (you reference their types). If not merged yet, code against the frozen contracts in master §5 — they won't change.

REQUIRED READING:
1. docs/plans/2026-04-17-hybrid-detection/00-master-plan.md  (§5.1)
2. docs/plans/2026-04-17-hybrid-detection/08-diagnostic-hud.md

MISSION
Two new files:
- android/app/src/main/java/com/iams/app/ui/debug/DiagnosticMetricsCollector.kt
- android/app/src/main/java/com/iams/app/ui/debug/HybridDiagnosticHud.kt

WHAT THE HUD SHOWS
ML Kit FPS / Backend FPS / Clock skew ms / RTT ms / Bound-Coast-MLKit-FB counts / Frame-sequence gap.
Each row turns red when past its warning threshold.

COLLECTOR API (frozen by this session's plan)
class DiagnosticMetricsCollector {
    data class Snapshot(...)
    fun recordMlkit(nowNs: Long)
    fun recordBackend(nowNs: Long, sequence: Int?)
    fun snapshot(tracks: List<HybridTrack>, skewMs: Long, rttMs: Long, nowNs: Long): Snapshot
}

HARD RULES
- Rolling window of 30 samples per stream for FPS.
- Reset lastSeqGap every 5s.
- `synchronized(this)` on collector mutations (two dispatchers write to it).
- HUD visible by default only in `BuildConfig.DEBUG`.
- Long-press on the video toggles visibility.
- No network calls; no file I/O; no Firebase.

DO NOT
- Do not wire the collector into the ViewModel — Session 06 does that (document the wiring snippet clearly in your commit or in the handoff notes section of your plan).
- Do not change the theme globally.
- Do not log from the HUD.

ACCEPTANCE
- Build passes.
- HUD renders in debug build within ~500ms of Live Feed opening.
- Long-press toggles on/off.
- No frame-rate drop with HUD on (verify in Android Studio Profiler).
- Release build: HUD invisible by default (confirm via `./gradlew assembleRelease`).

WHEN DONE
- Commit per section 11 of 08-diagnostic-hud.md.
- Update the handoff notes in 06-live-feed-integration.md if you must adjust any wiring signatures (ideally none).
```

---

## SESSION 09 — Hybrid Fallback Controller

```
You are implementing Session 09 of the IAMS hybrid detection rollout.

Repo: /Users/cjjutba/Projects/iams
Branch: feat/architecture-redesign

PREREQUISITE (loose)
Works best once Sessions 01 and 04 are merged (you call matcher methods and read timeSync). If not, code against the frozen contracts in master §5.

REQUIRED READING:
1. docs/plans/2026-04-17-hybrid-detection/00-master-plan.md  (§5.1, §5.4)
2. docs/plans/2026-04-17-hybrid-detection/09-fallback-controller.md

MISSION
Create one file:
- android/app/src/main/java/com/iams/app/hybrid/HybridFallbackController.kt

PUBLIC API
enum class HybridMode { HYBRID, BACKEND_ONLY, DEGRADED, OFFLINE }
class HybridFallbackController(matcher, timeSync, scope, config = Config()) {
    data class Config(mlkitSilenceTimeoutMs: Long = 2000, wsSilenceTimeoutMs: Long = 3000, rttWarningMs: Long = 1500)
    val mode: StateFlow<HybridMode>
    fun reportMlkitUpdate(nowNs: Long)
    fun reportBackendMessage(nowNs: Long)
    fun reportWsConnected()
    fun reportWsDisconnected()
    fun start()
    fun stop()
}

STATE MACHINE
- Every 500ms, compute `mlkitStale` and `wsStale` from `AtomicLong` timestamps.
- HYBRID ↔ DEGRADED / BACKEND_ONLY / OFFLINE transitions emit matcher.onBackendDisconnected() or onBackendReconnected() as appropriate.
- Log transitions (single line), not every tick.

HARD RULES
- `AtomicLong` for timestamps (lock-free from callers).
- Ticker runs on the injected `scope` (ViewModel scope — auto-cancelled on onCleared).
- `reportMlkitUpdate` is called on EVERY sink emission, even if face list is empty (covered-camera case must not trigger BACKEND_ONLY).

DO NOT
- Do not restart the ML Kit sink.
- Do not try to reconnect the WebSocket.
- Do not log on every tick.
- Do not add a circuit breaker.

ACCEPTANCE
- Build passes.
- Small inline test (separate file or top-of-file @Test) verifies the transition matrix: steady → stop mlkit → BACKEND_ONLY; resume → HYBRID; cut WS → DEGRADED; cut both → OFFLINE.
- `matcher.onBackendDisconnected()` called exactly once per DEGRADED/OFFLINE entry.
- Coroutine cleanly cancelled on scope close.

WHEN DONE
- Commit per section 10 of 09-fallback-controller.md.
```

---

## SESSION 10 — Integration Validation, Tuning, and Documentation

```
You are implementing Session 10 of the IAMS hybrid detection rollout.

Repo: /Users/cjjutba/Projects/iams
Branch: feat/architecture-redesign

PREREQUISITES (ALL must be merged)
Sessions 01, 02, 03, 04, 05, 06, 07, 08, 09.
If any are missing, STOP and report which ones.

REQUIRED READING:
1. docs/plans/2026-04-17-hybrid-detection/00-master-plan.md  (full)
2. docs/plans/2026-04-17-hybrid-detection/10-integration-validation-docs.md  (full)
3. Current CLAUDE.md (project root) — to plan the doc updates

MISSION
Ship the feature. Three deliverables:

1. EXECUTE the on-device test matrix (§3 of 10-integration-validation-docs.md) on a real device (or at minimum, an emulator with a fake RTSP source). Log results.

2. TUNE threshold values based on the test run. Record final values in:
   docs/plans/2026-04-17-hybrid-detection/TUNING.md
   Apply any value changes via a small diff on whichever file owns the default (MatcherConfig in HybridTypes.kt or HybridFallbackController.Config).

3. UPDATE DOCS:
   - CLAUDE.md — architecture diagram, §1 text about ML Kit on phone, add Hybrid Detection row to "Key Technical Details".
   - docs/main/implementation.md — new subsection on hybrid detection with links back to this plan.
   - memory/lessons.md — append master lessons per §5 of 10-integration-validation-docs.md.

ENVIRONMENT
Local Docker only. Start with:
    docker compose up -d
    docker compose exec api-gateway python -m scripts.seed_data

For the test video without a real camera:
    ffmpeg -stream_loop -1 -re -i test_video.mp4 -c:v libx264 -f rtsp rtsp://localhost:8554/test/raw

HARD RULES
- DO NOT deploy to VPS. Project policy: local-only validation, user explicitly authorises prod deploys.
- DO NOT change implementation code unless tuning reveals a concrete bug (file a follow-up issue instead).
- DO NOT skip scenario 3.6 (30-min stability test) — it's the main regression catcher. Run it in background while you work on docs.
- If the golden-path test (§3.1) fails, STOP and report; don't patch without the user's input.

ACCEPTANCE
- All §3 scenarios documented pass/fail in TUNING.md.
- CLAUDE.md, docs/main/implementation.md, memory/lessons.md updated.
- Final PR green on CI.
- Report handed off to user with:
  * Device(s) tested
  * Pass/fail per scenario
  * Final threshold values + why
  * Any known follow-ups

WHEN DONE
- Commit per section 11 of 10-integration-validation-docs.md.
- Do NOT merge to main and do NOT run deploy/deploy.sh — leave that for the user.
```

---

## Copy-paste workflow

1. Pick a session matching your parallel slot.
2. Start a new Claude Code session at `/Users/cjjutba/Projects/iams`.
3. Paste the entire block for that session (including the triple-backticks — Claude will read the content).
4. Let it run. When done, review the PR.
5. Merge in the dependency order listed in the master plan §9:
   `01, 02, 04, 05, 07, 08, 09` (any order) → `03` → `06` → `10`.

If any session goes off the rails (redefining frozen types, touching out-of-scope files), stop it early and re-paste the prompt — the hard rules exist specifically to catch those drifts.
