# Session 06 — FacultyLiveFeedScreen Integration

**Deliverable:** wire Session 01 (matcher) + 02 (sink) + 03 (overlay) + 04 (time-sync) into the actual Faculty Live Feed screen behind a feature flag.
**Blocks:** session 10.
**Blocked by:** sessions 02, 03, 04, 05 (all must be merged before integration can be validated on-device).
**Est. effort:** 4 hours.

Read [00-master-plan.md](00-master-plan.md) §5 (all contracts).

---

## 1. Scope

Three things:

1. Add the `HYBRID_DETECTION_ENABLED` BuildConfig flag.
2. Instantiate `FaceIdentityMatcher` + `TimeSyncClient` in `FacultyLiveFeedViewModel`; feed ML Kit output (from Session 02 callbacks) and backend WS output (from the existing WS handler) into the matcher.
3. Swap `InterpolatedTrackOverlay` for `HybridTrackOverlay` when the flag is on; keep the legacy path as fallback.

This session is the "glue". It does not implement new logic — just wires existing, merged components.

## 2. Files

| Path | New? |
|------|------|
| `android/app/build.gradle.kts` | MODIFIED (BuildConfig flag) |
| `android/app/src/main/java/com/iams/app/ui/faculty/FacultyLiveFeedViewModel.kt` | MODIFIED |
| `android/app/src/main/java/com/iams/app/ui/faculty/FacultyLiveFeedScreen.kt` | MODIFIED |

## 3. Implementation steps

### Step 1 — BuildConfig flag

In `android/app/build.gradle.kts` under `defaultConfig`:

```kotlin
buildConfigField("boolean", "HYBRID_DETECTION_ENABLED", "true")
```

Override in release if needed later. Ensure `buildFeatures { buildConfig = true }` is already present.

### Step 2 — ViewModel injection + state

In `FacultyLiveFeedViewModel.kt`, add constructor params (Hilt-injected):

```kotlin
@Inject constructor(
    // ...existing
    private val matcher: FaceIdentityMatcher,   // bind in HybridModule (see Step 4)
    private val timeSync: TimeSyncClient,
)
```

Expose:
```kotlin
val hybridTracks: StateFlow<List<HybridTrack>> = matcher.tracks
val timeSyncSkewMs: StateFlow<Long> = timeSync.skewMs
val timeSyncRttMs: StateFlow<Long> = timeSync.lastRttMs
```

In `init`:
```kotlin
if (BuildConfig.HYBRID_DETECTION_ENABLED) {
    timeSync.start(baseUrl = /* existing backend URL */)
}
```

In `onCleared`:
```kotlin
if (BuildConfig.HYBRID_DETECTION_ENABLED) {
    matcher.reset()
    timeSync.stop()
}
```

### Step 3 — Callback plumbing in ViewModel

```kotlin
private val matcherDispatcher = Dispatchers.Default.limitedParallelism(1) // single-thread per master §5.5

fun onMlKitFaces(faces: List<MlKitFace>) {
    viewModelScope.launch(matcherDispatcher) {
        matcher.onMlKitUpdate(faces, System.nanoTime())
    }
}

fun onMlKitFrameSize(width: Int, height: Int) {
    _frameDimensions.value = width to height
}

// Existing WS handler for frame_update — add this line after parsing tracks:
viewModelScope.launch(matcherDispatcher) {
    matcher.onBackendFrame(tracks, serverTimeMs, System.nanoTime())
}

// Existing WS connection-state handler — add:
viewModelScope.launch(matcherDispatcher) {
    if (connected) matcher.onBackendReconnected() else matcher.onBackendDisconnected()
}
```

Parse `serverTimeMs` from the WS payload (Session 05 added it). Nullable.

### Step 4 — Hilt module

Create `android/app/src/main/java/com/iams/app/di/HybridModule.kt`:

```kotlin
@Module
@InstallIn(ViewModelComponent::class)
abstract class HybridModule {
    @Binds
    abstract fun bindMatcher(impl: DefaultFaceIdentityMatcher): FaceIdentityMatcher
}
```

Make `DefaultFaceIdentityMatcher` `@Inject constructor()`-able. Scope: `@ViewModelScoped` so each Live Feed session gets a fresh matcher.

### Step 5 — Screen composable swap

In `FacultyLiveFeedScreen.kt` around line 413:

```kotlin
val hybridTracks by viewModel.hybridTracks.collectAsStateWithLifecycle()
val (frameW, frameH) = /* existing frameDimensions */

NativeWebRtcVideoPlayer(
    whepUrl = uiState.videoUrl,
    modifier = Modifier.fillMaxSize(),
    onError = { error -> viewModel.onVideoError(error) },
    onVideoReady = { isVideoReady = true },
    onMlKitFacesUpdate = viewModel::onMlKitFaces,
    onMlKitFrameSize = viewModel::onMlKitFrameSize,
    enableMlKit = BuildConfig.HYBRID_DETECTION_ENABLED,
)

if (BuildConfig.HYBRID_DETECTION_ENABLED) {
    HybridTrackOverlay(
        tracks = hybridTracks,
        modifier = Modifier.fillMaxSize(),
        videoFrameWidth = frameW.takeIf { it > 0 } ?: 896,
        videoFrameHeight = frameH.takeIf { it > 0 } ?: 512,
        isVideoReady = isVideoReady,
    )
} else {
    InterpolatedTrackOverlay(
        tracks = tracks,
        modifier = Modifier.fillMaxSize(),
        videoFrameWidth = frameW.takeIf { it > 0 } ?: 896,
        videoFrameHeight = frameH.takeIf { it > 0 } ?: 512,
        isVideoReady = isVideoReady,
    )
}
```

## 4. Acceptance criteria

- [ ] `HYBRID_DETECTION_ENABLED=true`: Live Feed shows green boxes that track faces smoothly at 30 fps; names appear under the right faces within 500 ms.
- [ ] `HYBRID_DETECTION_ENABLED=false`: Legacy behaviour — the existing `InterpolatedTrackOverlay` runs exactly as before. No regression.
- [ ] Disabling Wi-Fi for 5 s does NOT freeze the boxes (they keep following faces via ML Kit). Names show in yellow/orange "Unknown" after 3 s coasting.
- [ ] Toggling airplane mode on & off during a live session: matcher recovers identity within 1 s of WS reconnect.
- [ ] Memory profile over 10 min: no upward slope in Java heap.
- [ ] Navigating away from the screen and back restarts the matcher cleanly (verified via logcat — matcher `reset()` called on `onCleared`).

## 5. Anti-goals

- Do not change the matcher, sink, overlay, or time-sync implementations. This session is glue.
- Do not add new WebSocket message types.
- Do not alter camera permissions logic.
- Do not ship a debug HUD here (Session 08 owns it).
- Do not implement fallback controller logic here (Session 09 owns it).

## 6. Handoff notes

**For Session 10:** this PR's green build + green smoke tests is the integration gate. Session 10 validates end-to-end behaviour after this merges.

## 7. Risks

- **Dispatcher deadlock:** keep matcher calls on `limitedParallelism(1)` of `Dispatchers.Default`. Never call the matcher from the `Main.immediate` context where Compose runs.
- **Hilt scope mismatch:** matcher must be `@ViewModelScoped`, not `@Singleton` — otherwise the bindings leak between Live Feed sessions.
- **BuildConfig caching:** if flipping the flag doesn't seem to take effect, run `./gradlew clean` before rebuilding.

## 8. Commit message template

```
hybrid(06): integrate matcher + sink + overlay into FacultyLiveFeedScreen

Wires FaceIdentityMatcher (01), MlKitFrameSink (02), HybridTrackOverlay (03),
and TimeSyncClient (04) into the live feed behind the HYBRID_DETECTION_ENABLED
BuildConfig flag. Legacy InterpolatedTrackOverlay path preserved as fallback.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## 9. Lessons

- One dispatcher, single-threaded, owns matcher calls. Cleaner than trying to make the matcher itself thread-safe.
- Feature flag from day one lets every subsequent session merge without fear.
