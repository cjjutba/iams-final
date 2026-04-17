package com.iams.app.hybrid

/**
 * One ML-Kit-tracked face fused with the backend identity that currently owns it.
 * Produced by [FaceIdentityMatcher.tracks]; consumed by HybridTrackOverlay (session 03).
 */
data class HybridTrack(
    val mlkitFaceId: Int,
    val bbox: FloatArray,
    val backendTrackId: Int?,
    val identity: HybridIdentity,
    val lastBoundAtNs: Long,
    val source: HybridSource,
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is HybridTrack) return false
        if (mlkitFaceId != other.mlkitFaceId) return false
        if (!bbox.contentEquals(other.bbox)) return false
        if (backendTrackId != other.backendTrackId) return false
        if (identity != other.identity) return false
        if (lastBoundAtNs != other.lastBoundAtNs) return false
        if (source != other.source) return false
        return true
    }

    override fun hashCode(): Int {
        var result = mlkitFaceId
        result = 31 * result + bbox.contentHashCode()
        result = 31 * result + (backendTrackId ?: 0)
        result = 31 * result + identity.hashCode()
        result = 31 * result + lastBoundAtNs.hashCode()
        result = 31 * result + source.hashCode()
        return result
    }
}

data class HybridIdentity(
    val userId: String?,
    val name: String?,
    val confidence: Float,
    val status: String,
)

enum class HybridSource {
    /** ML Kit sees a face but the backend has not (yet) claimed it. Label: "Detecting…". */
    MLKIT_ONLY,

    /** Backend track matched to an ML Kit face via IoU; identity is fresh. */
    BOUND,

    /** Backend match has gone stale but is still within the identity-hold window. */
    COASTING,

    /**
     * Backend reported a face that no ML Kit face covers (out-of-frame for ML Kit, or
     * ML Kit missed it on this cycle). Bbox comes from the backend. Ensures the overlay
     * stays in sync with the "Detected" tab even when ML Kit and SCRFD disagree.
     */
    BACKEND_ONLY,

    /** Backend WS is offline AND the track has no recent ML Kit evidence. Placeholder. */
    FALLBACK,
}

data class MatcherConfig(
    val iouBindThreshold: Float = 0.40f,
    val iouReleaseThreshold: Float = 0.20f,
    val identityHoldMs: Long = 3_000L,
    val firstBindGraceMs: Long = 500L,
    val maxClockSkewMs: Long = 1_500L,
    val backendStalenessMs: Long = 2_000L,
)
