# Session 02 — Wire MlKitFrameSink into NativeWebRtcVideoPlayer

**Deliverable:** attach the existing `MlKitFrameSink` to the WebRTC `VideoTrack`, expose its `faces` and `frameSize` StateFlows to composable callers.
**Blocks:** session 06.
**Blocked by:** nothing (but merges after sessions 01, 03 since they define consumer contracts).
**Est. effort:** 2 hours.

Read [00-master-plan.md](00-master-plan.md) §5.1 and §5.5 before coding.

---

## 1. Scope

`MlKitFrameSink.kt` is fully implemented and unreferenced. This session wires it into `NativeWebRtcVideoPlayer.kt` as a *second* sink on the `VideoTrack` (alongside the existing `SurfaceViewRenderer`) and exposes its output via composable parameters so a parent can lift the state.

No ML Kit behaviour changes here. No matcher here. No overlay here. Just: attach sink → expose flows.

## 2. Files

| Path | New? |
|------|------|
| `android/app/src/main/java/com/iams/app/ui/components/NativeWebRtcVideoPlayer.kt` | MODIFIED |

One file. That's it.

## 3. Current state to understand

`NativeWebRtcVideoPlayer` is a composable that wraps a WebRTC `SurfaceViewRenderer`. When a `VideoTrack` arrives via the WHEP negotiation, it calls `videoTrack.addSink(surfaceViewRenderer)`. We need to add a second `addSink` call for `MlKitFrameSink`.

`MlKitFrameSink` exposes:
- `val faces: StateFlow<List<MlKitFace>>`
- `val frameSize: StateFlow<Pair<Int, Int>>`
- `override fun close()`

## 4. Implementation steps

### Step 1 — Add callback parameters to the composable

```kotlin
@Composable
fun NativeWebRtcVideoPlayer(
    whepUrl: String,
    modifier: Modifier = Modifier,
    onError: (String) -> Unit = {},
    onVideoReady: () -> Unit = {},
    // NEW:
    onMlKitFacesUpdate: (List<MlKitFace>) -> Unit = {},
    onMlKitFrameSize: (Int, Int) -> Unit = { _, _ -> },
    enableMlKit: Boolean = true,
)
```

Defaults keep every existing call site working (Session 06 will flip `enableMlKit` based on BuildConfig).

### Step 2 — Create the sink alongside the renderer

Locate the `remember { SurfaceViewRenderer(...) }` block. Add:

```kotlin
val mlKitSink = remember(enableMlKit) {
    if (enableMlKit) MlKitFrameSink() else null
}
```

### Step 3 — Attach the sink when the `VideoTrack` binds

Find the code that calls `videoTrack.addSink(surfaceViewRenderer)`. Immediately after:

```kotlin
mlKitSink?.let { videoTrack.addSink(it) }
```

And on cleanup (wherever `removeSink` or `dispose` happens for the surface renderer):

```kotlin
mlKitSink?.let { videoTrack.removeSink(it) }
```

Do not call `close()` on the sink here — `DisposableEffect` handles that (step 5).

### Step 4 — Pipe the StateFlows out

```kotlin
LaunchedEffect(mlKitSink) {
    mlKitSink?.faces?.collect { onMlKitFacesUpdate(it) }
}
LaunchedEffect(mlKitSink) {
    mlKitSink?.frameSize?.collect { (w, h) -> onMlKitFrameSize(w, h) }
}
```

Two separate `LaunchedEffect`s so one stalling won't block the other.

### Step 5 — Dispose properly

In the composable's `DisposableEffect(Unit) { onDispose { ... } }`:

```kotlin
mlKitSink?.close()
```

Must come BEFORE the `SurfaceViewRenderer.release()` call so the sink stops receiving frames first.

## 5. Acceptance criteria

- [ ] Build passes (`./gradlew assembleDebug`).
- [ ] When the composable is on-screen with a live WebRTC stream, logcat shows `MlKitFrameSink` receiving frames (already has log line at TAG `"MlKitFrameSink"`).
- [ ] `onMlKitFacesUpdate` callback fires at ~15 fps (sink processes every 2nd frame; check via counting invocations with a wallclock).
- [ ] `onMlKitFrameSize` fires at least once per session with non-zero dimensions.
- [ ] Navigating away from the Live Feed screen and back does not leak ML Kit resources (check `faceDetector` closed via `mlKitSink.close()`).
- [ ] `enableMlKit = false` path: no sink created, no callbacks fired, no memory overhead.
- [ ] Existing `InterpolatedTrackOverlay` path (legacy) still works when `enableMlKit = false`.

## 6. Anti-goals (do NOT do)

- Do not modify `MlKitFrameSink.kt`.
- Do not touch `InterpolatedTrackOverlay.kt` or `HybridTrackOverlay.kt`.
- Do not call the matcher from here — the composable only emits raw ML Kit data. Session 06 wires matcher between these callbacks and the overlay.
- Do not add logging beyond `Log.d` on errors; the sink already has its own logging.
- Do not change the WHEP / WebRTC negotiation logic.

## 7. Handoff notes

**For Session 06:** call site will be:
```kotlin
NativeWebRtcVideoPlayer(
    whepUrl = uiState.videoUrl,
    onMlKitFacesUpdate = viewModel::onMlKitFaces,
    onMlKitFrameSize = viewModel::onMlKitFrameSize,
    enableMlKit = BuildConfig.HYBRID_DETECTION_ENABLED,
    ...
)
```

**For Session 10 (validation):** test on both the slow-WiFi case (video choppy) and the high-FPS case (steady 30 fps) to verify the ML Kit sink doesn't starve the surface renderer.

## 8. Risks

- **Race on `videoTrack` binding:** the existing code assumes a single sink. Verify the WebRTC API allows two sinks on one track (`PeerConnectionFactory` / `VideoTrack.addSink` docs confirm it's a list). If dual-sink hits a crash, log full stack trace — not a new-session issue, but a WebRTC native issue.
- **Frame buffer pressure:** the sink `retains` and `releases` frames correctly (already reviewed). Still monitor via `adb shell dumpsys meminfo` during a 10-min session.
- **Thread safety of `onMlKitFacesUpdate`:** the sink emits on its internal executor; `StateFlow.collect` moves it onto the composable's coroutine dispatcher, so the callback runs on `Dispatchers.Main.immediate`. Session 06 must forward to the matcher via `Dispatchers.Default`.

## 9. Commit message template

```
hybrid(02): wire MlKitFrameSink into NativeWebRtcVideoPlayer

Attach the existing (unused) MlKitFrameSink as a second VideoSink on the
WebRTC VideoTrack, expose its faces/frameSize StateFlows via callback
parameters so parent composables can feed the FaceIdentityMatcher.

Gated behind enableMlKit (default true) so session 06 can feature-flag.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## 10. Lessons for post-implementation memory

- `MlKitFrameSink` was already correct — just unreferenced. Sometimes the best code is already in the repo.
- WebRTC `VideoTrack` supports multiple sinks natively. No fan-out wrapper needed.
