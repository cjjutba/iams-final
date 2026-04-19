package com.iams.app.ui.components

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithCache
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.sp
import com.iams.app.hybrid.HybridIdentity
import com.iams.app.hybrid.HybridSource
import com.iams.app.hybrid.HybridTrack
import kotlinx.coroutines.launch

/** Minimum interval between renders: ~33.3 ms = 30 fps. */
private const val FRAME_INTERVAL_NS = 33_333_333L

/** Suppress MLKIT_ONLY tracks younger than this to hide transient false positives. */
private const val MLKIT_ONLY_GRACE_NS = 800_000_000L

/** Remove render-state entries absent for longer than this (prevents map growth). */
private const val PRUNE_AFTER_NS = 500_000_000L

/**
 * Brand-new tracks render "Detecting…" (ORANGE) for this long before the backend's
 * `status="unknown"` is trusted and the box flips RED. At 5 fps production broadcasts
 * that is ~10 backend updates — plenty of time to surface a registered user as
 * recognised before committing to "Unknown".
 */
private const val INITIAL_UNKNOWN_GRACE_NS = 2_000_000_000L

/**
 * If a track was recognised within this window, any subsequent `status="unknown"`
 * from the backend is treated as a momentary re-verify dip and rendered "Detecting…"
 * instead of flickering to RED.
 */
private const val POST_RECOGNIZED_STICKY_NS = 2_000_000_000L

/**
 * Hybrid overlay: ML Kit owns positions, backend owns identities.
 *
 * Inputs come pre-matched via [HybridTrack]. The overlay is pure drawing code —
 * it does not read from the matcher directly and does not manage matcher lifecycle.
 *
 * Unlike [InterpolatedTrackOverlay], no snap interpolation is applied here. ML Kit
 * already delivers new positions at 30 fps, so boxes are drawn directly from
 * `track.bbox`. Fade-in (150 ms) and fade-out (300 ms) mirror the legacy overlay for
 * visual continuity. Source is colour-coded per [HybridSource].
 */
@Composable
fun HybridTrackOverlay(
    tracks: List<HybridTrack>,
    modifier: Modifier = Modifier,
    videoFrameWidth: Int = 0,
    videoFrameHeight: Int = 0,
    isVideoReady: Boolean = true,
    showCoasting: Boolean = true,
) {
    val textMeasurer = rememberTextMeasurer()
    val renderStates = remember { mutableMapOf<Int, TrackRenderState>() }
    val scope = rememberCoroutineScope()

    // Invalidation trigger — incremented at 30 fps to drive drawWithCache.
    var drawTick by remember { mutableIntStateOf(0) }

    // Overlay-wide fade-in. Prevents boxes appearing on a black screen during
    // WebRTC negotiation. Same behaviour as InterpolatedTrackOverlay.
    val overlayAlpha = remember { Animatable(0f) }
    LaunchedEffect(isVideoReady) {
        if (isVideoReady) {
            overlayAlpha.animateTo(1f, tween(200))
        } else {
            overlayAlpha.snapTo(0f)
        }
    }

    // 30 fps render loop.
    LaunchedEffect(Unit) {
        var lastRenderNanos = System.nanoTime()
        while (true) {
            withFrameNanos { now ->
                if (now - lastRenderNanos >= FRAME_INTERVAL_NS) {
                    lastRenderNanos = now
                    drawTick++
                }
            }
        }
    }

    // React to matcher output.
    LaunchedEffect(tracks) {
        val now = System.nanoTime()
        val activeIds = tracks.mapTo(HashSet()) { it.mlkitFaceId }

        // Start fade-out for disappeared faces.
        for ((id, state) in renderStates) {
            if (id !in activeIds && !state.fadingOut) {
                state.fadingOut = true
                scope.launch { state.alpha.animateTo(0f, tween(300)) }
            }
        }

        // Prune states absent for > 500 ms and fully faded.
        renderStates.entries.removeAll { (id, state) ->
            id !in activeIds &&
                (now - state.lastSeenNs) > PRUNE_AFTER_NS &&
                state.alpha.value < 0.01f
        }

        for (track in tracks) {
            val existing = renderStates[track.mlkitFaceId]
            if (existing == null) {
                val fresh = TrackRenderState(
                    alpha = Animatable(0f),
                    createdNs = now,
                    lastSeenNs = now,
                )
                renderStates[track.mlkitFaceId] = fresh
                scope.launch { fresh.alpha.animateTo(1f, tween(150)) }
            } else {
                existing.lastSeenNs = now
                if (existing.fadingOut) {
                    existing.fadingOut = false
                    scope.launch { existing.alpha.animateTo(1f, tween(150)) }
                } else if (existing.alpha.value < 1f) {
                    scope.launch { existing.alpha.animateTo(1f, tween(150)) }
                }
            }
        }
    }

    @Suppress("UNUSED_EXPRESSION")
    androidx.compose.foundation.layout.Spacer(
        modifier = modifier
            .fillMaxSize()
            .drawWithCache {
                drawTick

                val canvasW = size.width
                val canvasH = size.height
                val cropOffsetX: Float
                val cropOffsetY: Float
                val renderW: Float
                val renderH: Float

                if (videoFrameWidth > 0 && videoFrameHeight > 0) {
                    val videoAspect = videoFrameWidth.toFloat() / videoFrameHeight.toFloat()
                    val canvasAspect = canvasW / canvasH
                    if (videoAspect > canvasAspect) {
                        renderH = canvasH
                        renderW = canvasH * videoAspect
                        cropOffsetX = (renderW - canvasW) / 2f
                        cropOffsetY = 0f
                    } else {
                        renderW = canvasW
                        renderH = canvasW / videoAspect
                        cropOffsetX = 0f
                        cropOffsetY = (renderH - canvasH) / 2f
                    }
                } else {
                    renderW = canvasW
                    renderH = canvasH
                    cropOffsetX = 0f
                    cropOffsetY = 0f
                }

                onDrawBehind {
                    val fade = overlayAlpha.value
                    if (fade < 0.01f) return@onDrawBehind

                    val now = System.nanoTime()

                    for (track in tracks) {
                        val state = renderStates[track.mlkitFaceId] ?: continue
                        val alpha = state.alpha.value * fade
                        if (alpha < 0.01f) continue

                        // Hide MLKIT_ONLY tracks that haven't existed long enough.
                        if (track.source == HybridSource.MLKIT_ONLY) {
                            val age = now - state.createdNs
                            if (age < MLKIT_ONLY_GRACE_NS) continue
                        }

                        // Caller may hide coasting boxes entirely.
                        if (track.source == HybridSource.COASTING && !showCoasting) continue

                        val left = track.bbox[0] * renderW - cropOffsetX
                        val top = track.bbox[1] * renderH - cropOffsetY
                        val right = track.bbox[2] * renderW - cropOffsetX
                        val bottom = track.bbox[3] * renderH - cropOffsetY
                        val boxWidth = right - left
                        val boxHeight = bottom - top
                        if (boxWidth < 2f || boxHeight < 2f) continue

                        // Three-state display. The backend now emits an explicit
                        // `recognition_state` field ("recognized" | "warming_up" |
                        // "unknown") that gates the overlay colour/label. The
                        // phone-side time grace below is only used as a fallback
                        // when the backend is an older build that doesn't send
                        // the field (nullable in TrackInfo for backward compat).
                        //
                        // Rationale — the time grace alone was only 2 s, which
                        // expired long before FAISS finished its warm-up retries
                        // for faces whose cosine hovered near RECOGNITION_THRESHOLD.
                        // The backend-driven signal holds "warming_up" until
                        // UNKNOWN_CONFIRM_ATTEMPTS consecutive misses *and* a
                        // best-seen cosine comfortably below threshold accumulate
                        // — so registered users never flash red and genuine
                        // strangers still get flagged within ~10-15 s.
                        //
                        // Defensive: if status="recognized" but the name is missing
                        // or literally "Unknown" (stale FAISS vector to a deleted
                        // user), treat the track as unknown-eligible rather than
                        // rendering a green box labelled "Unknown".
                        val recognisedName = track.identity.name
                            ?.takeIf {
                                track.identity.status == "recognized" &&
                                    it.isNotBlank() &&
                                    !it.equals("Unknown", ignoreCase = true)
                            }
                        val backendSaysUnknown = track.identity.status == "unknown" ||
                            (track.identity.status == "recognized" &&
                                (track.identity.name.isNullOrBlank() ||
                                    track.identity.name.equals("Unknown", ignoreCase = true)))

                        if (recognisedName != null) {
                            state.lastRecognizedAtNs = now
                        }
                        val trackAgeNs = now - state.createdNs
                        val withinInitialGrace = trackAgeNs < INITIAL_UNKNOWN_GRACE_NS
                        val withinPostRecognizedSticky = state.lastRecognizedAtNs != 0L &&
                            (now - state.lastRecognizedAtNs) < POST_RECOGNIZED_STICKY_NS

                        // Resolve the display verdict. Preference order:
                        //   1. Backend tri-state (`recognition_state`) when present.
                        //   2. Legacy time-grace fallback for older backends.
                        val backendState = track.identity.recognitionState
                        val verdict = when (backendState) {
                            "recognized" -> if (recognisedName != null) Verdict.RECOGNIZED else Verdict.WARMING
                            "warming_up" -> Verdict.WARMING
                            "unknown" -> Verdict.UNKNOWN
                            else -> when {
                                recognisedName != null -> Verdict.RECOGNIZED
                                backendSaysUnknown && !withinInitialGrace && !withinPostRecognizedSticky ->
                                    Verdict.UNKNOWN
                                else -> Verdict.WARMING
                            }
                        }

                        val (label, boxColor) = when (verdict) {
                            Verdict.RECOGNIZED ->
                                firstNameOnly(recognisedName ?: track.identity.name.orEmpty()) to
                                    Color(0xFF4CAF50).copy(alpha = alpha)
                            Verdict.UNKNOWN ->
                                "Unknown" to Color(0xFFE53935).copy(alpha = alpha)
                            Verdict.WARMING ->
                                "Detecting…" to Color(0xFFFF9800).copy(alpha = alpha)
                        }

                        drawRect(
                            color = boxColor,
                            topLeft = Offset(left, top),
                            size = Size(boxWidth, boxHeight),
                            style = Stroke(width = 2.5f),
                        )

                        // Full-length label. Let it extend past the bounding-box width if
                        // the name is longer; only cap at the canvas edge so it can't run
                        // off-screen. This replaces the old `maxWidthPx = boxWidth` that
                        // caused long names to render as "Chri…" / "Unk…" / "Det…".
                        drawNameLabel(
                            textMeasurer = textMeasurer,
                            label = label,
                            x = left,
                            y = top,
                            color = boxColor,
                            alpha = alpha,
                            maxWidthPx = (canvasW - left).coerceAtLeast(1f),
                        )
                    }
                }
            }
    )
}

// ---------------------------------------------------------------------------
// State + helpers
// ---------------------------------------------------------------------------

private class TrackRenderState(
    val alpha: Animatable<Float, *>,
    val createdNs: Long,
    var lastSeenNs: Long,
    /** Nanos of the most recent frame we rendered this track as "recognized" (0 = never). */
    var lastRecognizedAtNs: Long = 0L,
    var fadingOut: Boolean = false,
)

/** Final colour/label verdict for one track in one render frame. */
private enum class Verdict { RECOGNIZED, WARMING, UNKNOWN }

/**
 * Recognised labels show only the first whitespace-delimited token of the supplied
 * name so the chip stays compact (e.g. "Juan Dela Cruz" → "Juan"). Falls back to the
 * original string if it contains no whitespace — protects against single-word names.
 */
private fun firstNameOnly(fullName: String): String {
    val trimmed = fullName.trim()
    if (trimmed.isEmpty()) return trimmed
    val first = trimmed.substringBefore(' ')
    return if (first.isNotEmpty()) first else trimmed
}

/**
 * Copy of [InterpolatedTrackOverlay]'s drawNameLabel, extended with a `maxWidthPx`
 * parameter so long names truncate with an ellipsis instead of overflowing the box.
 */
private fun DrawScope.drawNameLabel(
    textMeasurer: TextMeasurer,
    label: String,
    x: Float,
    y: Float,
    color: Color,
    alpha: Float,
    maxWidthPx: Float = Float.POSITIVE_INFINITY,
) {
    val padH = 6f
    val padV = 3f
    val constraints = if (maxWidthPx.isFinite() && maxWidthPx > padH * 2) {
        Constraints(maxWidth = (maxWidthPx - padH * 2).toInt().coerceAtLeast(1))
    } else {
        Constraints()
    }
    val textResult = textMeasurer.measure(
        text = AnnotatedString(label),
        style = TextStyle(color = Color.White.copy(alpha = alpha), fontSize = 11.sp),
        overflow = TextOverflow.Ellipsis,
        maxLines = 1,
        constraints = constraints,
    )
    val labelW = textResult.size.width + padH * 2
    val labelH = textResult.size.height + padV * 2

    drawRect(
        color = color.copy(alpha = 0.8f * alpha),
        topLeft = Offset(x, y - labelH),
        size = Size(labelW, labelH),
    )

    drawText(
        textLayoutResult = textResult,
        topLeft = Offset(x + padH, y - labelH + padV),
    )
}

// ---------------------------------------------------------------------------
// Preview — synthetic HybridTracks, no backend or matcher required.
// ---------------------------------------------------------------------------

@Preview(widthDp = 400, heightDp = 300)
@Composable
private fun HybridTrackOverlayPreview() {
    val now = System.nanoTime()
    val sampleTracks = listOf(
        HybridTrack(
            mlkitFaceId = 1,
            bbox = floatArrayOf(0.10f, 0.20f, 0.35f, 0.65f),
            backendTrackId = 101,
            identity = HybridIdentity(
                userId = "u1",
                name = "Juan Dela Cruz",
                confidence = 0.92f,
                status = "recognized",
            ),
            lastBoundAtNs = now,
            source = HybridSource.BOUND,
        ),
        HybridTrack(
            mlkitFaceId = 2,
            bbox = floatArrayOf(0.42f, 0.30f, 0.62f, 0.70f),
            backendTrackId = 102,
            identity = HybridIdentity(
                userId = "u2",
                name = "Maria Concepcion Dela Fuente",
                confidence = 0.81f,
                status = "recognized",
            ),
            lastBoundAtNs = now - 2_500_000_000L,
            source = HybridSource.COASTING,
        ),
        HybridTrack(
            mlkitFaceId = 3,
            bbox = floatArrayOf(0.70f, 0.25f, 0.92f, 0.70f),
            backendTrackId = null,
            identity = HybridIdentity(
                userId = null,
                name = null,
                confidence = 0f,
                status = "unknown",
            ),
            lastBoundAtNs = 0L,
            source = HybridSource.MLKIT_ONLY,
        ),
    )

    HybridTrackOverlay(
        tracks = sampleTracks,
        videoFrameWidth = 1280,
        videoFrameHeight = 720,
        isVideoReady = true,
    )
}
