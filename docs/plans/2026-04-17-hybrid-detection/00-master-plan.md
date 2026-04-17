# Hybrid Detection + Recognition — Master Plan

**Date:** 2026-04-17
**Branch:** `feat/architecture-redesign` (current) → merge target `main`
**Parallelism target:** 10 concurrent Claude Code sessions
**Total wall-clock target:** ≤ 8 hours (vs 2-3 days serial)

---

## 1. Executive Summary

Today the IAMS live-feed is **backend-authoritative**: all face detection and recognition runs in the FastAPI backend (SCRFD + ByteTrack + ArcFace + FAISS at 20 fps), and the Android app interpolates box positions at 30 fps. This is accurate and simple but has three failure modes:

1. **WebSocket stutter** → boxes freeze on the phone.
2. **Fast head motion** → boxes visibly lag (50–100 ms behind the face).
3. **Backend CPU saturation** (concurrent sessions) → PROCESSING_FPS drops and everyone sees it.

**Target architecture (hybrid):** keep the backend as the **identity source of truth**, but hand the phone the **position source of truth** via ML Kit running on the WebRTC `VideoSink`. We bind the two streams with a sticky IoU matcher so each ML Kit face carries the name the backend assigns to the nearest backend track.

Good news: `[MlKitFrameSink.kt](../../../android/app/src/main/java/com/iams/app/webrtc/MlKitFrameSink.kt)` is already fully implemented. It's unreferenced. About 85 % of the work is wiring + glue code. The remaining 15 % is the matcher + fallback behaviour, which is exactly what the 10 sessions split up.

---

## 2. Current vs Target Architecture

### Current (backend-authoritative)
```
WebRTC video ──► SurfaceViewRenderer (draws frames, 30fps)
                        │
                        └── (no ML on phone during live feed)

Backend 20fps:  Frame → SCRFD → ByteTrack → ArcFace → FAISS
                        │
                        └─► WebSocket {track_id, bbox, name} ──► InterpolatedTrackOverlay (snap @30fps)
```

### Target (hybrid)
```
WebRTC video ──► SurfaceViewRenderer (renders video)
              └► MlKitFrameSink (every 2nd frame → ~15fps face detection, emits MlKitFace list)
                        │                                         ▲
                        ▼                                         │
              FaceIdentityMatcher  ◄─────────────────  Backend WS {track_id, bbox, name, server_time_ms}
                        │
                        ▼
              HybridTrackOverlay (draws at ML Kit cadence, labels from matcher)
```

**Invariant:** ML Kit owns *where* the box is; backend owns *who is in it*. Matcher sticks the two together per ML Kit track ID.

---

## 3. Dependency Graph

```
                    ┌─────────────────────────────────┐
                    │ Session 01  FaceIdentityMatcher │  (pure Kotlin, no deps)
                    └──────┬──────────────────────┬───┘
                           │                      │
┌──────────────────────┐   │                      │    ┌─────────────────────────┐
│ Session 02  Sink     │   │                      │    │ Session 07  Matcher     │
│ wiring (player)      │   │                      │    │ unit tests              │
└──────┬───────────────┘   │                      │    └─────────────────────────┘
       │                   │                      │
       │                   ▼                      ▼
       │          ┌─────────────────────────────────────┐
       │          │ Session 03  HybridTrackOverlay      │
       │          └──────┬──────────────────────────────┘
       │                 │
┌──────┴─────┐    ┌──────┴────────┐    ┌────────────────────┐
│ Session 04 │    │ Session 08    │    │ Session 09         │
│ TimeSync   │    │ Diagnostic    │    │ Fallback           │
│ (phone)    │    │ HUD           │    │ controller         │
└──────┬─────┘    └───────────────┘    └──────┬─────────────┘
       │                                      │
┌──────┴──────────────────────────────────────┴───────────────┐
│ Session 05  Backend WS protocol additions (server_time_ms)  │
└──────┬───────────────────────────────────────────────────────┘
       │
       ▼
┌───────────────────────────────────────────────────────────────┐
│ Session 06  FacultyLiveFeedScreen integration                 │
└──────┬────────────────────────────────────────────────────────┘
       │
       ▼
┌───────────────────────────────────────────────────────────────┐
│ Session 10  Integration validation + tuning + docs            │
└───────────────────────────────────────────────────────────────┘
```

**Parallelizable immediately (no code deps):** 01, 02, 04, 05, 07, 08, 09 (against contracts).
**Blocks on 01:** 03.
**Blocks on 02 + 03 + 04 + 05:** 06.
**Blocks on all:** 10.

To keep parallelism maximal, **all public contracts are frozen in this master plan (§6)**. Each session implements against the contract even before its upstream sessions merge, then integrates at rebase time.

---

## 4. Session Index

| # | Plan file | Surface touched | Status |
|---|-----------|-----------------|--------|
| 01 | [01-matcher-engine.md](01-matcher-engine.md) | `android/.../hybrid/FaceIdentityMatcher.kt` (new) | Ready |
| 02 | [02-mlkit-sink-wiring.md](02-mlkit-sink-wiring.md) | `NativeWebRtcVideoPlayer.kt` (modified) | Ready |
| 03 | [03-hybrid-track-overlay.md](03-hybrid-track-overlay.md) | `ui/components/HybridTrackOverlay.kt` (new) | Ready |
| 04 | [04-time-sync-utility.md](04-time-sync-utility.md) | `data/sync/TimeSyncClient.kt` (new) | Ready |
| 05 | [05-backend-protocol-additions.md](05-backend-protocol-additions.md) | `backend/.../realtime_pipeline.py` (modified) | Ready |
| 06 | [06-live-feed-integration.md](06-live-feed-integration.md) | `FacultyLiveFeedScreen.kt` + ViewModel (modified) | Ready |
| 07 | [07-matcher-unit-tests.md](07-matcher-unit-tests.md) | `androidTest/.../FaceIdentityMatcherTest.kt` (new) | Ready |
| 08 | [08-diagnostic-hud.md](08-diagnostic-hud.md) | `ui/debug/HybridDiagnosticHud.kt` (new) | Ready |
| 09 | [09-fallback-controller.md](09-fallback-controller.md) | `ui/hybrid/HybridFallbackController.kt` (new) | Ready |
| 10 | [10-integration-validation-docs.md](10-integration-validation-docs.md) | E2E tests + tuning doc | Ready |

Each session doc is **self-contained**. A Claude Code session given just that one file plus this master plan should be able to finish its slice without reading the others.

---

## 5. Shared Contracts (FROZEN — do not change without updating all sessions)

### 5.1 Kotlin data classes (package `com.iams.app.hybrid`)

These are the types every session codes against. Session 01 **writes** them. All other Android sessions **import** them.

```kotlin
// Emitted by MlKitFrameSink (already exists in com.iams.app.webrtc.MlKitFace).
// Session 01 must NOT redefine — it must import com.iams.app.webrtc.MlKitFace.
data class MlKitFace(
    val x1: Float, val y1: Float, val x2: Float, val y2: Float,  // normalized 0..1
    val faceId: Int?                                              // ML Kit tracking ID, nullable if tracking lost
)

// Emitted by backend WS (already exists in com.iams.app.data.model.TrackInfo).
// Session 01 must NOT redefine — it must import com.iams.app.data.model.TrackInfo.
data class TrackInfo(
    val trackId: Int,
    val bbox: FloatArray,            // [x1,y1,x2,y2] normalized 0..1
    val velocity: FloatArray,        // [vx,vy,vw,vh] normalized units/sec
    val name: String?,
    val confidence: Float,
    val userId: String?,
    val status: String,              // "recognized" | "unknown" | "pending"
    val serverTimeMs: Long? = null,  // NEW — set by Session 05, nullable for backward compat
)

// NEW. Produced by FaceIdentityMatcher.observe(). Consumed by HybridTrackOverlay.
data class HybridTrack(
    val mlkitFaceId: Int,            // ML Kit tracking ID — stable identifier
    val bbox: FloatArray,            // latest ML Kit normalized bbox
    val backendTrackId: Int?,        // nearest backend track, null if unbound
    val identity: HybridIdentity,    // see below
    val lastBoundAtNs: Long,         // monotonic ns when last matched to a backend track
    val source: HybridSource,        // MLKIT_ONLY | BOUND | COASTING | FALLBACK
)

data class HybridIdentity(
    val userId: String?,
    val name: String?,
    val confidence: Float,
    val status: String,              // mirrors TrackInfo.status
)

enum class HybridSource {
    MLKIT_ONLY,   // box from ML Kit, no backend identity yet (first ~500ms of new face)
    BOUND,        // box from ML Kit, identity from a freshly-bound backend track
    COASTING,     // box from ML Kit, identity held from a now-stale backend binding (<3s)
    FALLBACK,     // box from backend (ML Kit offline/unavailable) — degraded mode
}

data class MatcherConfig(
    val iouBindThreshold: Float = 0.40f,
    val iouReleaseThreshold: Float = 0.20f,
    val identityHoldMs: Long = 3_000L,
    val firstBindGraceMs: Long = 500L,
    val maxClockSkewMs: Long = 1_500L,
    val backendStalenessMs: Long = 2_000L,
)
```

### 5.2 Matcher public API (Session 01)

```kotlin
interface FaceIdentityMatcher {
    /** Observable stream of per-ML-Kit-face matched tracks. Emits every ML Kit update. */
    val tracks: StateFlow<List<HybridTrack>>

    /** Push latest ML Kit output (called from the sink's StateFlow.collect). */
    fun onMlKitUpdate(faces: List<MlKitFace>, frameTimestampNs: Long)

    /** Push latest backend frame (called from WS message handler). */
    fun onBackendFrame(tracks: List<TrackInfo>, serverTimeMs: Long?, receivedAtNs: Long)

    /** Called when backend WS disconnects — matcher switches to FALLBACK mode. */
    fun onBackendDisconnected()

    /** Called when backend WS reconnects. */
    fun onBackendReconnected()

    /** Reset all internal state (e.g., when leaving the screen). */
    fun reset()
}

class DefaultFaceIdentityMatcher(
    private val config: MatcherConfig = MatcherConfig(),
    private val clock: () -> Long = { System.nanoTime() },
) : FaceIdentityMatcher
```

### 5.3 Backend WebSocket protocol (Session 05)

Backwards-compatible additions to `frame_update` message:

```json
{
  "type": "frame_update",
  "timestamp": 1234567.890,
  "server_time_ms": 1744876543210,   // NEW — unix epoch ms, for clock skew calc
  "frame_sequence": 1523,             // NEW — monotonic counter, for gap detection
  "frame_size": [896, 512],
  "tracks": [{...}],
  "fps": 19.8,
  "processing_ms": 15.2
}
```

Phone-side handling rule: if `server_time_ms` is missing, matcher treats skew as 0 ms (legacy backend).

### 5.4 Time-sync contract (Session 04)

```kotlin
interface TimeSyncClient {
    /** Current estimate of (server_epoch_ms - device_epoch_ms). 0 if not yet synced. */
    val skewMs: StateFlow<Long>

    /** Last measured round-trip ms. -1 if not yet measured. */
    val lastRttMs: StateFlow<Long>

    fun start(baseUrl: String)
    fun stop()
}
```

Uses `GET /api/v1/health/time` which returns `{"server_time_ms": <long>}` (Session 05 adds this endpoint).

### 5.5 Threading model (FROZEN)

- **WebRTC decode thread:** `MlKitFrameSink.onFrame()` — do not block, already optimised.
- **ML Kit single-thread executor:** face detection runs here, emits on `_faces` StateFlow.
- **Main/Default dispatcher:** matcher `onMlKitUpdate` and `onBackendFrame` calls. Matcher internals are NOT thread-safe — callers must serialise. Use a single `Dispatchers.Default` coroutine in the ViewModel.
- **Compose main thread:** `HybridTrackOverlay` reads `matcher.tracks` state flow.

---

## 6. Success Criteria

| # | Criterion | How to verify |
|---|-----------|---------------|
| SC-1 | Boxes track faces at ≥ 30 fps perceived smoothness | Manual: rapid head-shake test — boxes should not lag > 33 ms |
| SC-2 | Names appear within 500 ms of face entering frame (pre-registered) | Manual: walk into frame, time from box appearing to name appearing |
| SC-3 | Boxes persist with no jitter when WS drops for ≤ 3 s | Manual: `adb shell svc wifi disable` while staring at a face |
| SC-4 | No identity swap between two side-by-side faces | Manual: two enrolled students standing adjacent, verify names stay stuck |
| SC-5 | Backend CPU unchanged ( ±5 % of current) | `docker stats` during 10-min session |
| SC-6 | Phone CPU < 40 % on mid-range device (Pixel 6a / Samsung A54) | Android Studio Profiler |
| SC-7 | Matcher unit tests ≥ 95 % line coverage | `./gradlew :app:jacocoTestReport` |
| SC-8 | Graceful fallback to backend-authoritative mode when ML Kit unavailable | Toggle airplane mode on camera permissions denied |

---

## 7. Testing Strategy

| Layer | Owner | Tool |
|-------|-------|------|
| Matcher logic | Session 07 | JUnit + kotlinx-coroutines-test, 25+ cases |
| Backend protocol | Session 05 | `pytest tests/test_websocket_protocol.py` |
| WebRTC sink | Session 02 | Manual + logcat verification (no unit test — requires SurfaceView) |
| End-to-end | Session 10 | Scripted manual test plan + optional Espresso instrumented test |

**Rule:** no session merges without its own tests green. Session 10 is the last to merge; it validates the whole stack.

---

## 8. Rollback Plan

All hybrid code lives behind a feature flag `HYBRID_DETECTION_ENABLED` (BuildConfig boolean, default `true` on `debug`, `false` on `release` for first shipment).

If live-feed regresses, set the flag to `false`. `FacultyLiveFeedScreen` picks the legacy `InterpolatedTrackOverlay` path when the flag is off.

Matcher, sink wiring, and all new files are additive. Only `FacultyLiveFeedScreen.kt` and `NativeWebRtcVideoPlayer.kt` are modified — both diffs are small and easy to revert.

No backend changes have semantic impact (Session 05 adds optional fields only).

---

## 9. Git / PR Strategy

Each session produces one PR targeting `feat/architecture-redesign`. PR naming:

```
hybrid(01): FaceIdentityMatcher engine
hybrid(02): wire MlKitFrameSink into NativeWebRtcVideoPlayer
hybrid(03): HybridTrackOverlay draws ML Kit boxes with backend identities
…
hybrid(10): E2E validation + tuning + docs
```

Merge order once all PRs are green:
1. 01, 02, 04, 05, 07, 08, 09 (any order — no file conflicts).
2. 03 (depends on 01).
3. 06 (depends on 02, 03, 04, 05).
4. 10 (depends on everything).

Conflict surface is minimal because sessions write to disjoint files (see table in §4).

---

## 10. Not In Scope

- Replacing ML Kit with MediaPipe / YOLO / TFLite custom models.
- Moving ArcFace recognition onto the phone.
- Backend detector changes (SCRFD → RetinaFace etc.).
- WebRTC codec or simulcast changes.
- Admin portal.
- Face registration flow (CameraX + ML Kit already work there).

Any of those are separate future plans.

---

## 11. First Execution Step

Per project rule: **write any lessons from §Lessons below to `memory/lessons.md` before starting implementation.**

---

## 12. Lessons

- **Don't redefine existing data types.** `MlKitFace` lives in `com.iams.app.webrtc`; `TrackInfo` lives in `com.iams.app.data.model`. Sessions must import these, not shadow them. Why: two parallel sessions drifting on the same type's shape = merge nightmare. How to apply: every Android session checks §5.1 before typing `data class`.
- **Freeze contracts in the master, not in code.** When 10 sessions run in parallel, the *document* is the integration point. A contract living only in one session's PR means nine other sessions are blocked. How to apply: before implementing, each session reads §5, uses those signatures verbatim, and files a "contract change" issue rather than editing unilaterally.
- **Feature-flag hybrid from day one.** Rollback path must exist before the first merge, not after a production incident. How to apply: Session 06 ships `BuildConfig.HYBRID_DETECTION_ENABLED` on its first commit, and `FacultyLiveFeedScreen` branches on it from that commit onward.
- **Clock skew is real but small.** Phones running NTP drift < 100 ms from reasonable servers. The 1.5 s `maxClockSkewMs` default is already 15× that — don't over-engineer. How to apply: Session 04 can ship a simple HTTP-based skew estimate; no NTP library needed.
- **ML Kit's `faceId` is the correct stickiness key.** It's stable across frames until the face leaves; the matcher should key its identity cache on it rather than on spatial position. How to apply: Session 01 uses a `Map<Int, IdentityBinding>` keyed on `faceId`, NOT on geometric centroids.
- **The backend is already optimized.** SCRFD + ByteTrack + drift detection + identity hold + coasting + adaptive enrollment is production-grade. Do not change it in this plan. How to apply: Session 05 only adds protocol fields; no pipeline logic changes.
