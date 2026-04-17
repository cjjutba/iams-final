# Session 07 — FaceIdentityMatcher Unit Tests

**Deliverable:** ≥ 25 JUnit tests covering the matcher logic, targeting ≥ 95 % line coverage.
**Blocks:** final merge of session 01 (tests gate the matcher).
**Blocked by:** session 01 (needs the types + interface to test).
**Est. effort:** 3 hours.

---

## 1. Scope

Comprehensive test suite for `DefaultFaceIdentityMatcher`. Pure JVM tests, no Robolectric, no instrumentation. Uses `kotlinx-coroutines-test` for controllable clocks.

## 2. Files

| Path | New? |
|------|------|
| `android/app/src/test/java/com/iams/app/hybrid/FaceIdentityMatcherTest.kt` | NEW |
| `android/app/src/test/java/com/iams/app/hybrid/IouMathTest.kt` | NEW |
| `android/app/src/test/java/com/iams/app/hybrid/MatcherFixtures.kt` | NEW (test-only builders) |

## 3. Dependencies

Add to `app/build.gradle.kts` `dependencies {}` if not present:

```kotlin
testImplementation("junit:junit:4.13.2")
testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.0")
testImplementation("com.google.truth:truth:1.4.2")
```

## 4. Test-fixture helpers (`MatcherFixtures.kt`)

```kotlin
fun mlkit(id: Int, x1: Float, y1: Float, x2: Float, y2: Float) =
    MlKitFace(x1, y1, x2, y2, faceId = id)

fun backend(
    trackId: Int,
    x1: Float, y1: Float, x2: Float, y2: Float,
    name: String? = null,
    status: String = "pending",
    userId: String? = null,
    confidence: Float = 0f,
) = TrackInfo(
    trackId = trackId,
    bbox = floatArrayOf(x1, y1, x2, y2),
    velocity = FloatArray(4),
    name = name, confidence = confidence, userId = userId, status = status,
    serverTimeMs = null,
)

class FakeClock(private var now: Long = 0L) : () -> Long {
    override fun invoke() = now
    fun advanceMs(ms: Long) { now += ms * 1_000_000L }
    fun advanceNs(ns: Long) { now += ns }
}
```

## 5. Test categories

### Category A: IoU math (`IouMathTest.kt`, 5 tests)
- Identical boxes → IoU == 1.0
- Disjoint boxes → IoU == 0.0
- Half-overlap → IoU == 1/3
- Zero-area A → IoU == 0.0
- Zero-area B → IoU == 0.0

### Category B: Basic matching (8 tests)
- Single ML Kit face, single backend track, high IoU → bound; identity propagates.
- No ML Kit faces → empty list emitted.
- No backend tracks → MLKIT_ONLY source (after 800 ms grace — but matcher doesn't enforce that; it only sets source from binding presence; overlay enforces 800 ms; verify source == MLKIT_ONLY).
- ML Kit face with `faceId == null` is skipped (no binding, not in emitted list).
- Two ML Kit faces, two backend tracks, clear spatial separation → correct pairing.
- IoU below `iouBindThreshold` → no binding (source MLKIT_ONLY).
- Recognised backend status propagates (identity.status == "recognized", identity.name correct).
- Reset clears all state; next update starts fresh.

### Category C: Sticky release (6 tests)
- After binding, a frame where IoU drops to 0.3 (between release 0.20 and bind 0.40) → binding preserved.
- After binding, a frame where IoU drops below `iouReleaseThreshold` → binding preserved until identity-hold expires (still in COASTING).
- Identity hold: 2 s after losing the backend track → source COASTING.
- Identity hold: 3.1 s after losing backend track → binding expired, source MLKIT_ONLY.
- ML Kit face disappears → binding removed (no memory leak).
- Same ML Kit face reappears (different `faceId`) → starts fresh.

### Category D: Identity swap prevention (3 tests)
- Two recognised students crossing paths: binding stays on original ML Kit face (no name-flipping).
- Backend returns different `trackId` with `status == "pending"` for same ML Kit face → old binding kept.
- Backend returns different `trackId` with `status == "recognized"` and waited > `firstBindGraceMs` → swap accepted.

### Category E: Connectivity (3 tests)
- `onBackendDisconnected` then `onMlKitUpdate` → sources are FALLBACK for new faces, COASTING for still-held bindings.
- `onBackendReconnected` then fresh `onBackendFrame` → bindings re-establish.
- Alternating disconnect/reconnect cycles → matcher state is stable (no leak, no crash).

### Category F: Emit diff (2 tests)
- Calling `onMlKitUpdate` with identical face list → still emits (new snapshot), but overlay-side deep equality holds.
- Rapid-fire 100 updates in a tight loop → no stack overflow, no thread issue (synchronous).

## 6. Example test

```kotlin
@Test
fun bindingRefreshesOnEachBackendFrame() {
    val clock = FakeClock()
    val m = DefaultFaceIdentityMatcher(clock = clock)

    // Frame 1: bind
    m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
    m.onBackendFrame(listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")), null, clock())

    assertThat(m.tracks.value).hasSize(1)
    assertThat(m.tracks.value[0].identity.name).isEqualTo("Alice")
    assertThat(m.tracks.value[0].source).isEqualTo(HybridSource.BOUND)

    // Frame 2: 200 ms later, same positions, no backend update
    clock.advanceMs(200)
    m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())

    // Still COASTING (within hold window, > 100 ms since last bind)
    assertThat(m.tracks.value[0].source).isEqualTo(HybridSource.COASTING)
    assertThat(m.tracks.value[0].identity.name).isEqualTo("Alice")

    // Frame 3: 3.1 s later
    clock.advanceMs(3_000)
    m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())

    // Past identity hold — binding expires
    assertThat(m.tracks.value[0].source).isEqualTo(HybridSource.MLKIT_ONLY)
    assertThat(m.tracks.value[0].identity.name).isNull()
}
```

## 7. Acceptance criteria

- [ ] `./gradlew :app:testDebugUnitTest` passes.
- [ ] 25+ tests, all green.
- [ ] Coverage report (`./gradlew :app:jacocoTestReport`) shows ≥ 95 % line coverage on `com.iams.app.hybrid.*` package.
- [ ] No flaky tests (run 5× locally, all green).
- [ ] Tests complete in < 2 s total.

## 8. Anti-goals

- Do not test the sink (would need Robolectric + WebRTC).
- Do not test the overlay (would need Compose Test — Session 10 may add screenshot tests).
- Do not use reflection to peek at private state — every test drives the public API.
- Do not add new public matcher methods for testability. Use injection.

## 9. Risks

- **StateFlow timing in tests:** calling `matcher.tracks.value` returns synchronous latest value. Don't use `first { }` suspend variant.
- **FloatArray equality:** when asserting bbox values use `assertThat(bbox).usingTolerance(0.001f).containsExactly(...)` or compare element-wise.

## 10. Commit message template

```
hybrid(07): unit tests for FaceIdentityMatcher (>=95% coverage)

25 JUnit tests covering IoU math, basic matching, sticky release,
identity-swap prevention, connectivity transitions, and emit diff.
Uses a FakeClock injection for deterministic time-based tests.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## 11. Lessons

- FakeClock > `runTest` virtual time for matchers that don't use `delay()` — simpler, no coroutine scope.
- Every edge case written down as a test is one less bug to diagnose in production.
