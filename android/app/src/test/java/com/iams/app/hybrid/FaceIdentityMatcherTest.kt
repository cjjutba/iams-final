package com.iams.app.hybrid

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class FaceIdentityMatcherTest {

    // region Category B: basic matching ---------------------------------------------------------

    @Test
    fun singleFaceBindsWithHighIou() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized", userId = "u-1", confidence = 0.92f)),
            null,
            clock(),
        )

        val t = m.tracks.value.single()
        assertThat(t.mlkitFaceId).isEqualTo(1)
        assertThat(t.backendTrackId).isEqualTo(100)
        assertThat(t.source).isEqualTo(HybridSource.BOUND)
        assertThat(t.identity.name).isEqualTo("Alice")
        assertThat(t.identity.userId).isEqualTo("u-1")
        assertThat(t.identity.status).isEqualTo("recognized")
        assertThat(t.identity.confidence).isWithin(1e-6f).of(0.92f)
    }

    @Test
    fun noMlKitFacesEmitsEmptyListWhenBackendAlsoEmpty() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(emptyList(), clock())
        m.onBackendFrame(emptyList(), null, clock())

        assertThat(m.tracks.value).isEmpty()
    }

    @Test
    fun backendOnlyTrackEmitsWhenMlKitHasNoFace() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        // ML Kit sees nothing, backend still reports a recognised face (e.g. ML Kit missed
        // a profile shot SCRFD found). Must emit a BACKEND_ONLY track so the overlay stays
        // in sync with the Detected tab.
        m.onMlKitUpdate(emptyList(), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized", userId = "u-1")),
            null,
            clock(),
        )

        val track = m.tracks.value.single()
        assertThat(track.source).isEqualTo(HybridSource.BACKEND_ONLY)
        assertThat(track.backendTrackId).isEqualTo(100)
        assertThat(track.identity.name).isEqualTo("Alice")
        assertThat(track.identity.status).isEqualTo("recognized")
        // mlkitFaceId is a synthetic render key; must be in the negative half so it can't
        // collide with real ML Kit ids on a future frame.
        assertThat(track.mlkitFaceId).isLessThan(0)
    }

    @Test
    fun noBackendTracksProducesMlkitOnly() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())

        val t = m.tracks.value.single()
        assertThat(t.source).isEqualTo(HybridSource.MLKIT_ONLY)
        assertThat(t.identity.name).isNull()
        assertThat(t.identity.status).isEqualTo("pending")
        assertThat(t.backendTrackId).isNull()
    }

    @Test
    fun nullFaceIdIsSkipped() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(
            listOf(
                mlkit(null, 0.1f, 0.1f, 0.3f, 0.3f),
                mlkit(7, 0.5f, 0.5f, 0.7f, 0.7f),
            ),
            clock(),
        )

        val tracks = m.tracks.value
        assertThat(tracks).hasSize(1)
        assertThat(tracks.single().mlkitFaceId).isEqualTo(7)
    }

    @Test
    fun twoFacesTwoTracksAreCorrectlyPaired() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(
            listOf(
                mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f),
                mlkit(2, 0.6f, 0.1f, 0.8f, 0.3f),
            ),
            clock(),
        )
        m.onBackendFrame(
            listOf(
                backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized"),
                backend(200, 0.6f, 0.1f, 0.8f, 0.3f, name = "Bob", status = "recognized"),
            ),
            null,
            clock(),
        )

        val byFaceId = m.tracks.value.associateBy { it.mlkitFaceId }
        assertThat(byFaceId[1]?.identity?.name).isEqualTo("Alice")
        assertThat(byFaceId[1]?.backendTrackId).isEqualTo(100)
        assertThat(byFaceId[2]?.identity?.name).isEqualTo("Bob")
        assertThat(byFaceId[2]?.backendTrackId).isEqualTo(200)
    }

    @Test
    fun iouBelowBindThresholdProducesSeparateMlkitAndBackendTracks() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        // Disjoint boxes so neither IoU thresholds trigger: no binding AND no spatial cover.
        m.onMlKitUpdate(listOf(mlkit(1, 0.0f, 0.0f, 0.10f, 0.10f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.80f, 0.80f, 0.95f, 0.95f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )

        val bySource = m.tracks.value.groupBy { it.source }
        // ML Kit face emits as MLKIT_ONLY (no nearby backend track to bind).
        val mlkit = bySource[HybridSource.MLKIT_ONLY]?.single()
        assertThat(mlkit?.mlkitFaceId).isEqualTo(1)
        assertThat(mlkit?.identity?.name).isNull()
        assertThat(mlkit?.backendTrackId).isNull()

        // Backend track emits as BACKEND_ONLY (no ML Kit face covers it).
        val backendOnly = bySource[HybridSource.BACKEND_ONLY]?.single()
        assertThat(backendOnly?.backendTrackId).isEqualTo(100)
        assertThat(backendOnly?.identity?.name).isEqualTo("Alice")
    }

    @Test
    fun recognizedStatusPropagates() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )

        val identity = m.tracks.value.single().identity
        assertThat(identity.status).isEqualTo("recognized")
        assertThat(identity.name).isEqualTo("Alice")
    }

    @Test
    fun resetClearsAllState() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")), null, clock())
        m.onBackendDisconnected()
        assertThat(m.tracks.value).isNotEmpty()

        m.reset()
        assertThat(m.tracks.value).isEmpty()

        // After reset the matcher behaves as fresh: same ML Kit face → MLKIT_ONLY (no stale Alice).
        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        val t = m.tracks.value.single()
        assertThat(t.source).isEqualTo(HybridSource.MLKIT_ONLY)
        assertThat(t.identity.name).isNull()
    }

    // endregion

    // region Category C: sticky release ---------------------------------------------------------

    @Test
    fun stickyReleasePreservesBindingBetweenReleaseAndBind() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        // Initial bind (IoU = 1.0).
        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )

        // Drift ML Kit slightly so IoU vs the (still-there) backend track is ~0.39
        // (below bind-threshold 0.40, above release-threshold 0.20).
        clock.advanceMs(50)
        m.onMlKitUpdate(listOf(mlkit(1, 0.15f, 0.15f, 0.35f, 0.35f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )

        val t = m.tracks.value.single()
        assertThat(t.identity.name).isEqualTo("Alice")
        assertThat(t.backendTrackId).isEqualTo(100)
    }

    @Test
    fun driftBelowReleaseThresholdKeepsIdentityInCoasting() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )

        // Big jump → IoU drops to 0 with backend. Still within identity-hold window.
        clock.advanceMs(500)
        m.onMlKitUpdate(listOf(mlkit(1, 0.7f, 0.7f, 0.9f, 0.9f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )

        val t = m.tracks.value.single()
        assertThat(t.source).isEqualTo(HybridSource.COASTING)
        assertThat(t.identity.name).isEqualTo("Alice")
    }

    @Test
    fun identityHoldTwoSecondsShowsCoasting() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )

        // 2 seconds of ML Kit frames with no backend → still within 3 s hold → COASTING.
        clock.advanceMs(2_000)
        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())

        val t = m.tracks.value.single()
        assertThat(t.source).isEqualTo(HybridSource.COASTING)
        assertThat(t.identity.name).isEqualTo("Alice")
    }

    @Test
    fun identityHoldExpiresAfterConfiguredWindow() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )

        // 3.1 s later → past identity-hold → binding expires → MLKIT_ONLY, identity cleared.
        clock.advanceMs(3_100)
        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())

        val t = m.tracks.value.single()
        assertThat(t.source).isEqualTo(HybridSource.MLKIT_ONLY)
        assertThat(t.identity.name).isNull()
        assertThat(t.backendTrackId).isNull()
    }

    @Test
    fun mlkitFaceDisappearingRemovesBinding() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )
        assertThat(m.tracks.value.single().identity.name).isEqualTo("Alice")

        // Face leaves ML Kit's view. Backend still reports the track → emit as BACKEND_ONLY
        // so the overlay continues to show the recognised identity until the backend drops
        // it on its next frame.
        m.onMlKitUpdate(emptyList(), clock())
        val afterDisappear = m.tracks.value.single()
        assertThat(afterDisappear.source).isEqualTo(HybridSource.BACKEND_ONLY)
        assertThat(afterDisappear.backendTrackId).isEqualTo(100)
        assertThat(afterDisappear.identity.name).isEqualTo("Alice")

        // Re-push the same ML Kit id without a new backend frame. The old binding was
        // cleared when the face disappeared; spatial coverage now suppresses the
        // BACKEND_ONLY emission so the user sees a single MLKIT_ONLY box at the ML Kit
        // position (the next backend frame will rebind it via greedy IoU).
        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        val after = m.tracks.value.single()
        assertThat(after.source).isEqualTo(HybridSource.MLKIT_ONLY)
        assertThat(after.identity.name).isNull()
    }

    @Test
    fun sameFaceReappearingWithDifferentFaceIdStartsFresh() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )

        // ML Kit loses tracking then re-acquires as a brand new ID at the same spot.
        m.onMlKitUpdate(emptyList(), clock())
        m.onMlKitUpdate(listOf(mlkit(9999, 0.1f, 0.1f, 0.3f, 0.3f)), clock())

        val t = m.tracks.value.single()
        assertThat(t.mlkitFaceId).isEqualTo(9999)
        assertThat(t.source).isEqualTo(HybridSource.MLKIT_ONLY)
        assertThat(t.identity.name).isNull()
    }

    // endregion

    // region Category D: identity-swap prevention ----------------------------------------------

    @Test
    fun crossingFacesKeepTheirIdentities() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(
            listOf(
                mlkit(1, 0.10f, 0.10f, 0.30f, 0.30f),
                mlkit(2, 0.60f, 0.10f, 0.80f, 0.30f),
            ),
            clock(),
        )
        m.onBackendFrame(
            listOf(
                backend(100, 0.10f, 0.10f, 0.30f, 0.30f, name = "Alice", status = "recognized"),
                backend(200, 0.60f, 0.10f, 0.80f, 0.30f, name = "Bob", status = "recognized"),
            ),
            null,
            clock(),
        )

        // Small mutual drift that does NOT cross the midpoint.
        clock.advanceMs(100)
        m.onMlKitUpdate(
            listOf(
                mlkit(1, 0.12f, 0.10f, 0.32f, 0.30f),
                mlkit(2, 0.58f, 0.10f, 0.78f, 0.30f),
            ),
            clock(),
        )
        m.onBackendFrame(
            listOf(
                backend(100, 0.12f, 0.10f, 0.32f, 0.30f, name = "Alice", status = "recognized"),
                backend(200, 0.58f, 0.10f, 0.78f, 0.30f, name = "Bob", status = "recognized"),
            ),
            null,
            clock(),
        )

        val byFaceId = m.tracks.value.associateBy { it.mlkitFaceId }
        assertThat(byFaceId[1]?.identity?.name).isEqualTo("Alice")
        assertThat(byFaceId[2]?.identity?.name).isEqualTo("Bob")
    }

    @Test
    fun pendingTrackWithinGraceDoesNotOverwriteRecognizedBinding() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )

        // 100 ms later a DIFFERENT backend track at the same place arrives with status=pending
        // (simulating a brief ByteTrack ID swap during occlusion).
        clock.advanceMs(100)
        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(200, 0.1f, 0.1f, 0.3f, 0.3f, name = null, status = "pending")),
            null,
            clock(),
        )

        val t = m.tracks.value.single()
        assertThat(t.backendTrackId).isEqualTo(100)
        assertThat(t.identity.name).isEqualTo("Alice")
        assertThat(t.identity.status).isEqualTo("recognized")
    }

    @Test
    fun recognizedTrackImmediatelyOverwritesOldBinding() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )

        // Backend now reports a different track id, but it's RECOGNIZED as Bob — trust it.
        clock.advanceMs(200)
        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(300, 0.1f, 0.1f, 0.3f, 0.3f, name = "Bob", status = "recognized")),
            null,
            clock(),
        )

        val t = m.tracks.value.single()
        assertThat(t.backendTrackId).isEqualTo(300)
        assertThat(t.identity.name).isEqualTo("Bob")
    }

    // endregion

    // region Category E: connectivity -----------------------------------------------------------

    @Test
    fun disconnectLeavesHeldBindingsCoastingAndNewFacesFallback() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        // Establish binding for face 1.
        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )

        m.onBackendDisconnected()

        // 200 ms later: face 1 still visible AND a new face 2 appears; no backend frames arrive.
        clock.advanceMs(200)
        m.onMlKitUpdate(
            listOf(
                mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f),
                mlkit(2, 0.6f, 0.6f, 0.8f, 0.8f),
            ),
            clock(),
        )

        val byId = m.tracks.value.associateBy { it.mlkitFaceId }
        assertThat(byId[1]?.source).isEqualTo(HybridSource.COASTING)
        assertThat(byId[1]?.identity?.name).isEqualTo("Alice")
        assertThat(byId[2]?.source).isEqualTo(HybridSource.FALLBACK)
        assertThat(byId[2]?.identity?.name).isNull()
    }

    @Test
    fun reconnectAllowsBindingsToReestablish() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())

        m.onBackendDisconnected()
        assertThat(m.tracks.value.single().source).isEqualTo(HybridSource.FALLBACK)

        m.onBackendReconnected()
        // After reconnect a fresh backend frame arrives; binding should establish normally.
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )

        val t = m.tracks.value.single()
        assertThat(t.source).isEqualTo(HybridSource.BOUND)
        assertThat(t.identity.name).isEqualTo("Alice")
    }

    @Test
    fun alternatingConnectivityIsStable() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )

        repeat(20) {
            m.onBackendDisconnected()
            m.onBackendReconnected()
        }

        // Pump a fresh backend frame and ensure state is still sane.
        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )
        val t = m.tracks.value.single()
        assertThat(t.source).isEqualTo(HybridSource.BOUND)
        assertThat(t.identity.name).isEqualTo("Alice")
    }

    // endregion

    // region Category F: emit diff --------------------------------------------------------------

    @Test
    fun identicalSnapshotsAreDeepEqual() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        val snap1 = m.tracks.value.toList()

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        val snap2 = m.tracks.value.toList()

        assertThat(snap1).isEqualTo(snap2)
        assertThat(snap1.single().bbox)
            .usingTolerance(1e-6)
            .containsExactly(0.1f, 0.1f, 0.3f, 0.3f).inOrder()
    }

    @Test
    fun rapidFireUpdatesDoNotBlowTheStack() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        repeat(100) { i ->
            val x1 = 0.1f + (i % 10) * 0.001f
            m.onMlKitUpdate(listOf(mlkit(1, x1, 0.1f, x1 + 0.2f, 0.3f)), clock())
        }

        // The matcher must still be responsive and in a consistent state.
        val t = m.tracks.value.single()
        assertThat(t.mlkitFaceId).isEqualTo(1)
        assertThat(t.source).isEqualTo(HybridSource.MLKIT_ONLY)
    }

    // endregion

    // region Extra: refresh + defaults ---------------------------------------------------------

    @Test
    fun bindingRefreshesOnEachBackendFrame() {
        val clock = FakeClock()
        val m = DefaultFaceIdentityMatcher(clock = clock)

        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        m.onBackendFrame(
            listOf(backend(100, 0.1f, 0.1f, 0.3f, 0.3f, name = "Alice", status = "recognized")),
            null,
            clock(),
        )
        assertThat(m.tracks.value.single().source).isEqualTo(HybridSource.BOUND)

        // 200 ms later without a backend update → COASTING.
        clock.advanceMs(200)
        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        assertThat(m.tracks.value.single().source).isEqualTo(HybridSource.COASTING)
        assertThat(m.tracks.value.single().identity.name).isEqualTo("Alice")

        // 3.1 s after the initial bind → expired, MLKIT_ONLY, identity gone.
        clock.advanceMs(3_000)
        m.onMlKitUpdate(listOf(mlkit(1, 0.1f, 0.1f, 0.3f, 0.3f)), clock())
        val t = m.tracks.value.single()
        assertThat(t.source).isEqualTo(HybridSource.MLKIT_ONLY)
        assertThat(t.identity.name).isNull()
    }

    @Test
    fun matcherConfigDefaultsMatchContract() {
        val cfg = MatcherConfig()
        assertThat(cfg.iouBindThreshold).isEqualTo(0.40f)
        assertThat(cfg.iouReleaseThreshold).isEqualTo(0.20f)
        assertThat(cfg.identityHoldMs).isEqualTo(3_000L)
        assertThat(cfg.firstBindGraceMs).isEqualTo(500L)
        assertThat(cfg.maxClockSkewMs).isEqualTo(1_500L)
        assertThat(cfg.backendStalenessMs).isEqualTo(2_000L)
    }

    @Test
    fun hybridTrackEqualityRespectsBboxContent() {
        val a = HybridTrack(
            mlkitFaceId = 1,
            bbox = floatArrayOf(0.1f, 0.1f, 0.3f, 0.3f),
            backendTrackId = 10,
            identity = HybridIdentity("u", "n", 1f, "recognized"),
            lastBoundAtNs = 42L,
            source = HybridSource.BOUND,
        )
        val b = HybridTrack(
            mlkitFaceId = 1,
            bbox = floatArrayOf(0.1f, 0.1f, 0.3f, 0.3f),
            backendTrackId = 10,
            identity = HybridIdentity("u", "n", 1f, "recognized"),
            lastBoundAtNs = 42L,
            source = HybridSource.BOUND,
        )
        val c = b.copy(bbox = floatArrayOf(0.2f, 0.1f, 0.3f, 0.3f))

        assertThat(a).isEqualTo(b)
        assertThat(a.hashCode()).isEqualTo(b.hashCode())
        assertThat(a).isNotEqualTo(c)
    }

    // endregion
}
