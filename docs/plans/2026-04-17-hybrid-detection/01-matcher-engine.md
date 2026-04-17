# Session 01 — FaceIdentityMatcher Engine

**Deliverable:** the pure-Kotlin matching engine that binds ML Kit faces to backend track identities.
**Blocks:** sessions 03, 07, 08, 09, 10.
**Blocked by:** nothing.
**Est. effort:** 3 hours.

Read [00-master-plan.md](00-master-plan.md) §5 before writing any code. All public types in §5.1 must match verbatim.

---

## 1. Scope

Implement `com.iams.app.hybrid.FaceIdentityMatcher` and its default implementation `DefaultFaceIdentityMatcher`, plus the shared types `HybridTrack`, `HybridIdentity`, `HybridSource`, `MatcherConfig`. This session owns the domain logic: **given ML Kit faces + backend tracks, decide which identity goes on each ML Kit face.**

This is pure JVM code (no Android imports, no Compose, no coroutines Dispatcher specifics). It can be unit-tested on a plain JUnit runner (see Session 07).

## 2. Files

| Path | New? |
|------|------|
| `android/app/src/main/java/com/iams/app/hybrid/FaceIdentityMatcher.kt` | NEW |
| `android/app/src/main/java/com/iams/app/hybrid/HybridTypes.kt` | NEW |
| `android/app/src/main/java/com/iams/app/hybrid/IouMath.kt` | NEW |

No other files touched. No existing files renamed.

## 3. Imports you need

```kotlin
import com.iams.app.webrtc.MlKitFace          // existing, do not redefine
import com.iams.app.data.model.TrackInfo      // existing, do not redefine
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
```

## 4. Implementation steps

### Step 1 — `HybridTypes.kt`
Copy the data classes and enum from master §5.1 (`HybridTrack`, `HybridIdentity`, `HybridSource`, `MatcherConfig`) verbatim. Do NOT add fields. Do NOT rename. Override `equals`/`hashCode` for `HybridTrack` to handle the `FloatArray` correctly (Compose will use this for diffing).

### Step 2 — `IouMath.kt`
Pure helper. Two functions:
```kotlin
/** IoU between two normalized [x1,y1,x2,y2] boxes. Returns 0f if either has zero area. */
fun iou(a: FloatArray, b: FloatArray): Float
/** IoU between [x1,y1,x2,y2] and (x1,y1,x2,y2) scalars (avoids array alloc). */
fun iou(ax1: Float, ay1: Float, ax2: Float, ay2: Float,
        bx1: Float, by1: Float, bx2: Float, by2: Float): Float
```
No null handling — callers guarantee well-formed boxes.

### Step 3 — `FaceIdentityMatcher.kt`

Internal binding state:
```kotlin
private data class Binding(
    var backendTrackId: Int,
    var identity: HybridIdentity,
    var lastBoundAtNs: Long,        // clock() when last IoU match succeeded
    var lastBackendSeenAtNs: Long,  // clock() when backend last reported this track
)
```

Internal state:
```kotlin
private val bindingsByMlkitId = HashMap<Int, Binding>()
private var latestMlkitFaces: List<MlKitFace> = emptyList()
private var latestBackendTracks: List<TrackInfo> = emptyList()
private var backendOnline = true
private val _tracks = MutableStateFlow<List<HybridTrack>>(emptyList())
override val tracks: StateFlow<List<HybridTrack>> = _tracks.asStateFlow()
```

### Step 4 — State transitions (the core algorithm)

`onMlKitUpdate(faces, frameTimestampNs)`:
1. Store `latestMlkitFaces = faces`.
2. Drop bindings whose `mlkitFaceId` is no longer in `faces` (face left the frame).
3. Recompute `_tracks.value` via `emitSnapshot()` (step 6).

`onBackendFrame(backendTracks, serverTimeMs, receivedAtNs)`:
1. Store `latestBackendTracks = backendTracks`.
2. Build cost matrix (ML Kit faces × backend tracks) of **negative IoU** (because Hungarian minimises).
3. Greedy assignment (Hungarian is overkill for N≤20):
   - Sort all (mlkit_i, backend_j, iou) tuples descending by IoU.
   - Walk the list; accept an assignment if neither side already assigned and `iou >= config.iouBindThreshold`.
4. For each accepted pair, update `bindingsByMlkitId[mlkitFaceId]`:
   - If existing binding and same `backendTrackId`: refresh `lastBoundAtNs` + update identity.
   - If existing binding and different `backendTrackId`: overwrite IF new binding's backend status is `recognized` OR old binding has been unbound for > `firstBindGraceMs`. Otherwise keep old (prevents name-flipping during occlusion).
   - If no existing binding: create one.
5. For ML Kit faces that did NOT get bound this round but HAD a previous binding with IoU >= `iouReleaseThreshold` to the same backend track: keep the binding (sticky behaviour during slight drift).
6. `emitSnapshot()`.

`onBackendDisconnected()`:
- `backendOnline = false`
- `emitSnapshot()` — sources become `FALLBACK` if no binding, `COASTING` if still within hold window.

`onBackendReconnected()`:
- `backendOnline = true`
- `emitSnapshot()`.

### Step 5 — `emitSnapshot()` (one function, produces new `_tracks.value`)

For each face in `latestMlkitFaces`:
```kotlin
val faceId = face.faceId ?: continue     // ML Kit didn't assign a tracking ID; skip
val binding = bindingsByMlkitId[faceId]
val now = clock()

val source = when {
    binding == null && !backendOnline    -> HybridSource.FALLBACK  // will be handled elsewhere; matcher emits MLKIT_ONLY
    binding == null                      -> HybridSource.MLKIT_ONLY
    (now - binding.lastBoundAtNs) < 100_000_000L           -> HybridSource.BOUND       // < 100ms old
    (now - binding.lastBoundAtNs) < (config.identityHoldMs * 1_000_000L) -> HybridSource.COASTING
    else -> {
        bindingsByMlkitId.remove(faceId); HybridSource.MLKIT_ONLY   // expired
    }
}

val identity = binding?.identity ?: HybridIdentity(null, null, 0f, "pending")
list += HybridTrack(
    mlkitFaceId = faceId,
    bbox = floatArrayOf(face.x1, face.y1, face.x2, face.y2),
    backendTrackId = binding?.backendTrackId,
    identity = identity,
    lastBoundAtNs = binding?.lastBoundAtNs ?: 0L,
    source = source,
)
```

When `!backendOnline` AND no ML Kit input exists (camera off), emit an empty list.

### Step 6 — `reset()`
Clears `bindingsByMlkitId`, `latestMlkitFaces`, `latestBackendTracks`. Sets `backendOnline = true`. Emits empty list.

## 5. Acceptance criteria

- [ ] Code compiles against the Android module (AGP build passes, no warnings).
- [ ] All types in master §5.1 present verbatim.
- [ ] No Android framework imports (`android.*`) in these three files.
- [ ] `FaceIdentityMatcher` interface exported; `DefaultFaceIdentityMatcher` is the only implementation.
- [ ] `tracks` StateFlow never emits duplicate objects for identical input (diff-stable).
- [ ] `reset()` leaves the matcher behaving identically to a fresh instance.
- [ ] No `TODO`, no `!!` on nullable fields outside the documented safe contexts.

## 6. Anti-goals (do NOT do)

- Do not implement clock sync. That's Session 04. Use the injected `clock: () -> Long` parameter.
- Do not touch `MlKitFrameSink`. That's Session 02.
- Do not touch the overlay composable. That's Session 03.
- Do not write unit tests. That's Session 07.
- Do not add a logger. Matcher is pure; any logging happens at the call site.
- Do not use `Dispatchers.*` — matcher is single-threaded by contract (master §5.5).

## 7. Handoff notes

**For Session 03 (overlay):** consume `matcher.tracks`. Every emission is a full snapshot; overlay can call `drawWithCache` and diff on `mlkitFaceId`.

**For Session 07 (tests):** constructor takes a mockable `clock: () -> Long` — advance it in tests instead of using real time.

**For Session 09 (fallback):** call `onBackendDisconnected()` / `onBackendReconnected()` from a heartbeat watchdog in the ViewModel.

## 8. Risks

- **IoU threshold tuning:** 0.40 bind / 0.20 release is a starting point. If Session 10 finds identity-swapping, raise bind to 0.50 and release to 0.30.
- **ML Kit drops `faceId=null`:** check early in `onMlKitUpdate`; don't create a binding for null-id faces.
- **Map mutation during emit:** always rebuild the list in a local `val list = mutableListOf<HybridTrack>()`, then `_tracks.value = list.toList()`. Don't expose the mutable instance.

## 9. Commit message template

```
hybrid(01): add FaceIdentityMatcher engine

Pure Kotlin matcher binding ML Kit face IDs to backend track identities via
IoU with sticky release and identity hold. Emits a StateFlow<List<HybridTrack>>
consumed by the HybridTrackOverlay (session 03).

No Android framework deps; tested in isolation by session 07.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## 10. Lessons for post-implementation memory

- Matcher isolation: keeping the matcher framework-free made unit testing trivial and also let it be used from any thread (not just the WebRTC thread).
- Greedy IoU ≠ Hungarian for N ≤ 20 faces: the maths converges fast enough that Hungarian adds complexity with no gain.
