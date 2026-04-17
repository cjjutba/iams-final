package com.iams.app.hybrid

import com.iams.app.data.model.TrackInfo
import com.iams.app.webrtc.MlKitFace
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Pure-Kotlin matcher that binds ML Kit face IDs to backend track identities.
 *
 * Invariant: ML Kit owns *where* a box is; backend owns *who* is in it. The matcher
 * sticks the two together per ML Kit `faceId` via greedy IoU assignment with a sticky
 * release threshold and a time-windowed identity hold.
 *
 * Threading: NOT thread-safe. Callers must serialise calls (master-plan §5.5).
 */
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
) : FaceIdentityMatcher {

    private data class Binding(
        var backendTrackId: Int,
        var identity: HybridIdentity,
        var lastBoundAtNs: Long,
        var lastBackendSeenAtNs: Long,
    )

    private val bindingsByMlkitId = HashMap<Int, Binding>()
    private var latestMlkitFaces: List<MlKitFace> = emptyList()
    private var latestBackendTracks: List<TrackInfo> = emptyList()
    private var backendOnline = true

    private val _tracks = MutableStateFlow<List<HybridTrack>>(emptyList())
    override val tracks: StateFlow<List<HybridTrack>> = _tracks.asStateFlow()

    override fun onMlKitUpdate(faces: List<MlKitFace>, frameTimestampNs: Long) {
        latestMlkitFaces = faces

        val activeIds = HashSet<Int>(faces.size)
        for (face in faces) {
            val id = face.faceId
            if (id != null) activeIds.add(id)
        }
        val iter = bindingsByMlkitId.entries.iterator()
        while (iter.hasNext()) {
            if (iter.next().key !in activeIds) iter.remove()
        }

        emitSnapshot()
    }

    override fun onBackendFrame(
        tracks: List<TrackInfo>,
        serverTimeMs: Long?,
        receivedAtNs: Long,
    ) {
        latestBackendTracks = tracks
        val faces = latestMlkitFaces
        val now = clock()

        // Build (mlkitIdx, backendIdx, iou) candidates above zero-area.
        val candidates = ArrayList<Candidate>(faces.size * tracks.size)
        for (mi in faces.indices) {
            val face = faces[mi]
            if (face.faceId == null) continue
            for (bi in tracks.indices) {
                val bb = tracks[bi].bbox
                if (bb.size < 4) continue
                val iouVal = iou(
                    face.x1, face.y1, face.x2, face.y2,
                    bb[0], bb[1], bb[2], bb[3],
                )
                if (iouVal > 0f) candidates.add(Candidate(mi, bi, iouVal))
            }
        }
        candidates.sortByDescending { it.iou }

        // Greedy assignment above the bind threshold.
        val assignedMlkit = HashSet<Int>()
        val assignedBackend = HashSet<Int>()
        for (c in candidates) {
            if (c.iou < config.iouBindThreshold) break
            if (c.mIdx in assignedMlkit || c.bIdx in assignedBackend) continue

            val face = faces[c.mIdx]
            val mlkitId = face.faceId ?: continue
            val bt = tracks[c.bIdx]
            applyBinding(mlkitId, bt, now)
            assignedMlkit.add(c.mIdx)
            assignedBackend.add(c.bIdx)
        }

        // Sticky release: unassigned ML Kit faces with prior binding still close enough
        // to their bound backend track keep that binding fresh (prevents premature COASTING
        // during slight drift between detection cycles).
        for (mi in faces.indices) {
            if (mi in assignedMlkit) continue
            val face = faces[mi]
            val mlkitId = face.faceId ?: continue
            val binding = bindingsByMlkitId[mlkitId] ?: continue
            val bt = tracks.firstOrNull { it.trackId == binding.backendTrackId } ?: continue
            val bb = bt.bbox
            if (bb.size < 4) continue
            val iouVal = iou(
                face.x1, face.y1, face.x2, face.y2,
                bb[0], bb[1], bb[2], bb[3],
            )
            if (iouVal >= config.iouReleaseThreshold) {
                binding.lastBoundAtNs = now
                binding.lastBackendSeenAtNs = now
            }
        }

        emitSnapshot()
    }

    override fun onBackendDisconnected() {
        backendOnline = false
        // Drop any cached backend tracks so BACKEND_ONLY boxes don't linger at stale
        // positions while the backend is down. ML-Kit-only boxes continue to draw.
        latestBackendTracks = emptyList()
        emitSnapshot()
    }

    override fun onBackendReconnected() {
        backendOnline = true
        emitSnapshot()
    }

    override fun reset() {
        bindingsByMlkitId.clear()
        latestMlkitFaces = emptyList()
        latestBackendTracks = emptyList()
        backendOnline = true
        _tracks.value = emptyList()
    }

    private fun applyBinding(mlkitId: Int, bt: TrackInfo, now: Long) {
        val newIdentity = HybridIdentity(
            userId = bt.userId,
            name = bt.name,
            confidence = bt.confidence,
            status = bt.status,
        )
        val existing = bindingsByMlkitId[mlkitId]
        when {
            existing == null -> {
                bindingsByMlkitId[mlkitId] = Binding(
                    backendTrackId = bt.trackId,
                    identity = newIdentity,
                    lastBoundAtNs = now,
                    lastBackendSeenAtNs = now,
                )
            }
            existing.backendTrackId == bt.trackId -> {
                existing.identity = newIdentity
                existing.lastBoundAtNs = now
                existing.lastBackendSeenAtNs = now
            }
            else -> {
                // Different backend track wants to claim this face. Allow only if the
                // newcomer is recognized OR the old binding has aged past the grace window.
                val ageMs = (now - existing.lastBoundAtNs) / 1_000_000L
                val shouldOverwrite =
                    bt.status == "recognized" || ageMs > config.firstBindGraceMs
                if (shouldOverwrite) {
                    existing.backendTrackId = bt.trackId
                    existing.identity = newIdentity
                    existing.lastBoundAtNs = now
                    existing.lastBackendSeenAtNs = now
                }
            }
        }
    }

    private fun emitSnapshot() {
        val now = clock()
        val faces = latestMlkitFaces
        val list = ArrayList<HybridTrack>(faces.size + latestBackendTracks.size)
        var expired: ArrayList<Int>? = null

        // Track which backend track IDs ended up represented via an ML Kit binding so we
        // don't also emit them as BACKEND_ONLY (otherwise the overlay draws two boxes on
        // the same face).
        val coveredBackendIds = HashSet<Int>()

        for (face in faces) {
            val faceId = face.faceId ?: continue
            val binding = bindingsByMlkitId[faceId]

            val source = when {
                binding == null && !backendOnline -> HybridSource.FALLBACK
                binding == null -> HybridSource.MLKIT_ONLY
                (now - binding.lastBoundAtNs) < BOUND_FRESHNESS_NS ->
                    HybridSource.BOUND
                (now - binding.lastBoundAtNs) < (config.identityHoldMs * NS_PER_MS) ->
                    HybridSource.COASTING
                else -> {
                    (expired ?: ArrayList<Int>().also { expired = it }).add(faceId)
                    HybridSource.MLKIT_ONLY
                }
            }

            val effectiveBinding = if (source == HybridSource.MLKIT_ONLY ||
                source == HybridSource.FALLBACK
            ) {
                if (expired?.contains(faceId) == true) null else binding
            } else {
                binding
            }

            val identity = effectiveBinding?.identity
                ?: HybridIdentity(null, null, 0f, "pending")

            effectiveBinding?.let { coveredBackendIds.add(it.backendTrackId) }

            list += HybridTrack(
                mlkitFaceId = faceId,
                bbox = floatArrayOf(face.x1, face.y1, face.x2, face.y2),
                backendTrackId = effectiveBinding?.backendTrackId,
                identity = identity,
                lastBoundAtNs = effectiveBinding?.lastBoundAtNs ?: 0L,
                source = source,
            )
        }

        expired?.forEach { bindingsByMlkitId.remove(it) }

        // Emit any backend tracks that have no ML Kit face covering them. Uses a relaxed
        // IoU floor (iouReleaseThreshold) to suppress near-duplicates where the ML Kit
        // face just barely failed to bind — without this the overlay would draw two
        // boxes on a single physical face.
        if (backendOnline) {
            for (bt in latestBackendTracks) {
                if (bt.trackId in coveredBackendIds) continue
                val bbox = bt.bbox
                if (bbox.size < 4) continue
                val bx1 = bbox[0].toFloat()
                val by1 = bbox[1].toFloat()
                val bx2 = bbox[2].toFloat()
                val by2 = bbox[3].toFloat()
                if ((bx2 - bx1) <= 0f || (by2 - by1) <= 0f) continue

                val spatiallyCoveredByMlkit = faces.any { f ->
                    f.faceId != null &&
                        iou(f.x1, f.y1, f.x2, f.y2, bx1, by1, bx2, by2) >= config.iouReleaseThreshold
                }
                if (spatiallyCoveredByMlkit) continue

                list += HybridTrack(
                    mlkitFaceId = backendOnlyRenderKey(bt.trackId),
                    bbox = floatArrayOf(bx1, by1, bx2, by2),
                    backendTrackId = bt.trackId,
                    identity = HybridIdentity(
                        userId = bt.userId,
                        name = bt.name,
                        confidence = bt.confidence,
                        status = bt.status,
                    ),
                    lastBoundAtNs = 0L,
                    source = HybridSource.BACKEND_ONLY,
                )
            }
        }

        _tracks.value = list
    }

    /**
     * Synthesise a stable, negative "render key" for a backend-only track so the overlay
     * can keep ML Kit faceIds (always non-negative) disjoint from backend-only markers.
     * Stability across frames means fade-in/out animations key correctly.
     */
    private fun backendOnlyRenderKey(backendTrackId: Int): Int {
        // Shift into the negative half of Int. Int.MIN_VALUE avoids overlap with 0.
        return Int.MIN_VALUE + (backendTrackId and 0x7FFFFFFF)
    }

    private data class Candidate(val mIdx: Int, val bIdx: Int, val iou: Float)

    private companion object {
        const val NS_PER_MS = 1_000_000L
        const val BOUND_FRESHNESS_NS = 100L * NS_PER_MS
    }
}
