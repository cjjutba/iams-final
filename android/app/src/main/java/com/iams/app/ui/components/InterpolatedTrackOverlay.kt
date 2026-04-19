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
import androidx.compose.ui.text.*
import androidx.compose.ui.unit.sp
import com.iams.app.data.model.TrackInfo
import kotlinx.coroutines.launch

/** Stale timeout: matches backend TRACK_LOST_TIMEOUT (2s). */
private const val STALE_TIMEOUT_NS = 2_000_000_000L

/** Identity hold: keep showing recognized identity for 3s after backend says unknown. */
private const val IDENTITY_HOLD_NS = 3_000_000_000L

/** Minimum interval between renders: ~33.3ms = 30fps. */
private const val FRAME_INTERVAL_NS = 33_333_333L

/**
 * Snap factor: how fast the display position converges to the backend target.
 * Applied per frame at 30fps. 0.6 = move 60% of remaining distance each frame.
 * At 30fps with 15fps backend: reaches 84% in 2 frames (~67ms), 97% in 4 frames.
 *
 * This is NOT prediction — the box always moves TOWARD the last known backend
 * position, never away from it. No drift possible by design.
 */
private const val SNAP_FACTOR = 0.6f

/**
 * Backend-authoritative face overlay with smooth snap tracking at 30fps.
 *
 * Design principle: the backend is the single source of truth for face positions.
 * The display layer's only job is to smoothly converge to the latest backend
 * position without jitter. No velocity extrapolation, no prediction, no drift.
 *
 * The box always moves TOWARD the target, never away. When the face moves,
 * the backend sends a new position every 100ms and the box smoothly snaps to it.
 * When the face is still, the box locks perfectly because current == target.
 *
 * Performance: 30fps render via drawWithCache (no Compose recomposition).
 */
@Composable
fun InterpolatedTrackOverlay(
    tracks: List<TrackInfo>,
    modifier: Modifier = Modifier,
    videoFrameWidth: Int = 0,
    videoFrameHeight: Int = 0,
    isVideoReady: Boolean = true
) {
    val textMeasurer = rememberTextMeasurer()
    val trackStates = remember { mutableMapOf<Int, TrackOverlayState>() }
    val coroutineScope = rememberCoroutineScope()

    // Invalidation trigger — incremented at 30fps to drive drawWithCache
    var drawTick by remember { mutableIntStateOf(0) }

    // Overlay-wide fade-in alpha. Starts at 0 (hidden) and animates to 1 when
    // isVideoReady becomes true. Prevents bounding boxes from appearing on a
    // black screen during WebRTC connection negotiation (~1-3s handshake).
    val overlayAlpha = remember { Animatable(0f) }
    LaunchedEffect(isVideoReady) {
        if (isVideoReady) {
            overlayAlpha.animateTo(1f, tween(200))
        } else {
            overlayAlpha.snapTo(0f)
        }
    }

    // 30fps render loop
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

    // Update targets when new WebSocket data arrives (~10fps).
    LaunchedEffect(tracks) {
        val now = System.nanoTime()
        val activeIds = tracks.map { it.trackId }.toSet()

        // Mark disappeared tracks for fade-out
        for ((id, state) in trackStates) {
            if (id !in activeIds && state.isAlive) {
                state.isAlive = false
                state.deathTimeNanos = now
                coroutineScope.launch { state.alpha.animateTo(0f, tween(300)) }
            }
        }

        // Remove fully faded tracks
        trackStates.keys.removeAll { id ->
            val s = trackStates[id]
            s != null && !s.isAlive && s.alpha.value < 0.01f
        }

        for (track in tracks) {
            val existing = trackStates[track.trackId]

            if (existing != null) {
                // Update target — the display position will smoothly snap toward this
                existing.targetX1 = track.bbox[0]
                existing.targetY1 = track.bbox[1]
                existing.targetX2 = track.bbox[2]
                existing.targetY2 = track.bbox[3]
                existing.lastUpdateNanos = now
                existing.confidence = track.confidence
                existing.isAlive = true

                // Identity hold logic
                val isIncomingRecognized = track.status == "recognized"
                    && !track.name.isNullOrEmpty() && track.name != "Unknown"
                if (isIncomingRecognized) {
                    existing.lastRecognizedName = track.name
                    existing.lastRecognizedTimeNanos = now
                }
                if (!isIncomingRecognized
                    && existing.lastRecognizedName != null
                    && (now - existing.lastRecognizedTimeNanos) < IDENTITY_HOLD_NS
                ) {
                    existing.name = existing.lastRecognizedName
                    existing.status = "recognized"
                    // Keep recognition_state consistent with the held status so
                    // the label still renders the held name, not "Unknown".
                    existing.recognitionState = "recognized"
                } else {
                    existing.name = track.name
                    existing.status = track.status
                    existing.recognitionState = track.recognitionState
                }

                if (existing.alpha.value < 1f) {
                    coroutineScope.launch { existing.alpha.animateTo(1f, tween(150)) }
                }
            } else {
                // New track — snap current to target immediately (no animation on first frame)
                val isNewRecognized = track.status == "recognized"
                    && !track.name.isNullOrEmpty() && track.name != "Unknown"
                val state = TrackOverlayState(
                    targetX1 = track.bbox[0], targetY1 = track.bbox[1],
                    targetX2 = track.bbox[2], targetY2 = track.bbox[3],
                    currentX1 = track.bbox[0], currentY1 = track.bbox[1],
                    currentX2 = track.bbox[2], currentY2 = track.bbox[3],
                    lastUpdateNanos = now,
                    createdNanos = now,
                    alpha = Animatable(1f),
                    name = track.name,
                    confidence = track.confidence,
                    status = track.status,
                    recognitionState = track.recognitionState,
                    lastRecognizedName = if (isNewRecognized) track.name else null,
                    lastRecognizedTimeNanos = if (isNewRecognized) now else 0L,
                )
                trackStates[track.trackId] = state
            }
        }
    }

    // Draw layer — runs at 30fps
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
                    // Overall fade multiplier — 0 until video is confirmed rendering.
                    // Skip drawing entirely when fully faded out (video not ready).
                    val fade = overlayAlpha.value
                    if (fade < 0.01f) return@onDrawBehind

                    val now = System.nanoTime()

                    for ((_, state) in trackStates) {
                        val alpha = state.alpha.value * fade
                        if (alpha < 0.01f) continue
                        if (state.status == "pending") continue

                        val isRecognizedTrack = state.status == "recognized"
                            && !state.name.isNullOrEmpty() && state.name != "Unknown"
                        val trackAge = now - state.createdNanos
                        if (!isRecognizedTrack && trackAge < 800_000_000L) continue

                        if (now - state.lastUpdateNanos > STALE_TIMEOUT_NS) continue

                        // Smooth snap: move current position toward target.
                        state.currentX1 += (state.targetX1 - state.currentX1) * SNAP_FACTOR
                        state.currentY1 += (state.targetY1 - state.currentY1) * SNAP_FACTOR
                        state.currentX2 += (state.targetX2 - state.currentX2) * SNAP_FACTOR
                        state.currentY2 += (state.targetY2 - state.currentY2) * SNAP_FACTOR

                        // Map to canvas coordinates
                        val left   = state.currentX1 * renderW - cropOffsetX
                        val top    = state.currentY1 * renderH - cropOffsetY
                        val right  = state.currentX2 * renderW - cropOffsetX
                        val bottom = state.currentY2 * renderH - cropOffsetY
                        val boxWidth = right - left
                        val boxHeight = bottom - top
                        if (boxWidth < 2f || boxHeight < 2f) continue

                        val isRecognized = state.status == "recognized"
                            && !state.name.isNullOrEmpty() && state.name != "Unknown"

                        // Tri-state verdict (matches HybridTrackOverlay semantics so
                        // the two overlays render the same labels/colors). Falls
                        // back to the legacy "green or orange-Unknown" rendering if
                        // the backend doesn't emit recognition_state yet.
                        val backendState = state.recognitionState
                        val (label, boxColor) = when {
                            isRecognized ->
                                state.name!! to Color(0xFF4CAF50).copy(alpha = alpha)
                            backendState == "warming_up" ->
                                "Detecting…" to Color(0xFFFF9800).copy(alpha = alpha)
                            backendState == "unknown" ->
                                "Unknown" to Color(0xFFE53935).copy(alpha = alpha)
                            else ->
                                // Legacy fallback for older backends without tri-state.
                                "Unknown" to Color(0xFFFF9800).copy(alpha = alpha)
                        }

                        drawRect(
                            color = boxColor,
                            topLeft = Offset(left, top),
                            size = Size(boxWidth, boxHeight),
                            style = Stroke(width = 2.5f)
                        )

                        drawNameLabel(textMeasurer, label, left, top, boxColor, alpha)
                    }
                }
            }
    )
}

// ---------------------------------------------------------------------------
// State + helpers
// ---------------------------------------------------------------------------

private class TrackOverlayState(
    // Target: latest backend position (single source of truth)
    var targetX1: Float, var targetY1: Float,
    var targetX2: Float, var targetY2: Float,
    // Current: display position that smoothly converges to target
    var currentX1: Float, var currentY1: Float,
    var currentX2: Float, var currentY2: Float,
    var lastUpdateNanos: Long,
    val createdNanos: Long,
    val alpha: Animatable<Float, *>,
    var name: String?,
    var confidence: Float,
    var status: String,
    /**
     * Tri-state verdict from the backend. Null when the backend is an older build
     * that doesn't emit `recognition_state`; callers then fall back to the
     * legacy status-only rendering (orange + "Unknown" label).
     */
    var recognitionState: String? = null,
    var isAlive: Boolean = true,
    var deathTimeNanos: Long = 0L,
    var lastRecognizedName: String? = null,
    var lastRecognizedTimeNanos: Long = 0L,
)

private fun DrawScope.drawNameLabel(
    textMeasurer: TextMeasurer,
    label: String,
    x: Float,
    y: Float,
    color: Color,
    alpha: Float,
) {
    val textResult = textMeasurer.measure(
        text = AnnotatedString(label),
        style = TextStyle(color = Color.White.copy(alpha = alpha), fontSize = 11.sp)
    )
    val padH = 6f; val padV = 3f
    val labelW = textResult.size.width + padH * 2
    val labelH = textResult.size.height + padV * 2

    drawRect(
        color = color.copy(alpha = 0.8f * alpha),
        topLeft = Offset(x, y - labelH),
        size = Size(labelW, labelH)
    )

    drawText(
        textLayoutResult = textResult,
        topLeft = Offset(x + padH, y - labelH + padV)
    )
}
