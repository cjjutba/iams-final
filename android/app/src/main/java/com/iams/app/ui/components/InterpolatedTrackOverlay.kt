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
private const val STALE_TIMEOUT_NS = 2_000_000_000L // 2s

/** Identity hold: keep showing recognized identity for 3s after backend says unknown. */
private const val IDENTITY_HOLD_NS = 3_000_000_000L // 3s

/**
 * Fast lerp factor. 0.55 = move 55% toward target each frame at 60fps.
 * Reaches 95% of target in ~2 frames (~33ms) — feels instant but smooth.
 * No drift because we lerp toward a fixed backend position, not a predicted one.
 */
private const val LERP_FACTOR = 0.55f

/**
 * Backend-authoritative face overlay with smooth tracking.
 *
 * All positions and identities come from the backend via WebSocket at ~10fps.
 * Fast lerp interpolation renders at 60fps for seamless box movement.
 * No velocity extrapolation — avoids drift. The box always converges to
 * exactly where SCRFD detected the face.
 *
 * Performance: Uses Modifier.drawWithCache to render at 60fps WITHOUT triggering
 * Compose recomposition. Only the draw phase runs each frame — no tree rebuild.
 */
@Composable
fun InterpolatedTrackOverlay(
    tracks: List<TrackInfo>,
    modifier: Modifier = Modifier,
    videoFrameWidth: Int = 0,
    videoFrameHeight: Int = 0
) {
    val textMeasurer = rememberTextMeasurer()
    // Plain map — NOT mutableStateMapOf (avoid Compose snapshot tracking overhead)
    val trackStates = remember { mutableMapOf<Int, TrackOverlayState>() }
    val coroutineScope = rememberCoroutineScope()

    // Invalidation trigger: incremented to force Canvas redraw without recomposition
    var drawTick by remember { mutableIntStateOf(0) }

    // Drive continuous 60fps rendering for smooth lerp.
    // withFrameNanos suspends until the next vsync, then we bump drawTick
    // which invalidates the drawWithCache block — NO Compose recomposition.
    LaunchedEffect(Unit) {
        while (true) {
            withFrameNanos { _ -> drawTick++ }
        }
    }

    // Update target positions when new WebSocket data arrives.
    // This runs at ~10fps (WebSocket rate), not 60fps.
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
                // Update target — lerp will smoothly move toward it
                existing.targetX1 = track.bbox[0]
                existing.targetY1 = track.bbox[1]
                existing.targetX2 = track.bbox[2]
                existing.targetY2 = track.bbox[3]
                existing.lastUpdateNanos = now
                existing.confidence = track.confidence
                existing.isAlive = true

                // Track the last time this track was recognized
                val isIncomingRecognized = track.status == "recognized"
                    && !track.name.isNullOrEmpty() && track.name != "Unknown"
                if (isIncomingRecognized) {
                    existing.lastRecognizedName = track.name
                    existing.lastRecognizedTimeNanos = now
                }

                // Identity hold: if backend says unknown but we saw recognized recently,
                // keep showing the recognized identity (belt-and-suspenders with backend hold)
                if (!isIncomingRecognized
                    && existing.lastRecognizedName != null
                    && (now - existing.lastRecognizedTimeNanos) < IDENTITY_HOLD_NS
                ) {
                    existing.name = existing.lastRecognizedName
                    existing.status = "recognized"
                } else {
                    existing.name = track.name
                    existing.status = track.status
                }

                if (existing.alpha.value < 1f) {
                    coroutineScope.launch { existing.alpha.animateTo(1f, tween(150)) }
                }
            } else {
                // New track — snap current to target (no lerp on first frame)
                val isNewRecognized = track.status == "recognized"
                    && !track.name.isNullOrEmpty() && track.name != "Unknown"
                val state = TrackOverlayState(
                    targetX1 = track.bbox[0],
                    targetY1 = track.bbox[1],
                    targetX2 = track.bbox[2],
                    targetY2 = track.bbox[3],
                    currentX1 = track.bbox[0],
                    currentY1 = track.bbox[1],
                    currentX2 = track.bbox[2],
                    currentY2 = track.bbox[3],
                    lastUpdateNanos = now,
                    createdNanos = now,
                    alpha = Animatable(1f),
                    name = track.name,
                    confidence = track.confidence,
                    status = track.status,
                    lastRecognizedName = if (isNewRecognized) track.name else null,
                    lastRecognizedTimeNanos = if (isNewRecognized) now else 0L,
                )
                trackStates[track.trackId] = state
            }
        }
    }

    // Use Spacer + drawWithCache: the draw block re-executes when drawTick changes
    // but does NOT trigger Compose recomposition — only the draw phase runs.
    @Suppress("UNUSED_EXPRESSION")
    androidx.compose.foundation.layout.Spacer(
        modifier = modifier
            .fillMaxSize()
            .drawWithCache {
                // Read drawTick inside cache block to invalidate on every frame
                drawTick

                val canvasW = size.width
                val canvasH = size.height

                // Compute aspect-fit crop offsets
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
                    val now = System.nanoTime()

                    for ((_, state) in trackStates) {
                        val alpha = state.alpha.value
                        if (alpha < 0.01f) continue
                        if (state.status == "pending") continue

                        // Grace period: don't show "Unknown" for brand-new tracks
                        val isRecognizedTrack = state.status == "recognized"
                            && !state.name.isNullOrEmpty() && state.name != "Unknown"
                        val trackAge = now - state.createdNanos
                        if (!isRecognizedTrack && trackAge < 800_000_000L) continue

                        // Stale check
                        if (now - state.lastUpdateNanos > STALE_TIMEOUT_NS) continue

                        // Fast lerp toward target
                        state.currentX1 += (state.targetX1 - state.currentX1) * LERP_FACTOR
                        state.currentY1 += (state.targetY1 - state.currentY1) * LERP_FACTOR
                        state.currentX2 += (state.targetX2 - state.currentX2) * LERP_FACTOR
                        state.currentY2 += (state.targetY2 - state.currentY2) * LERP_FACTOR

                        // Map to canvas coordinates
                        val left = state.currentX1 * renderW - cropOffsetX
                        val top = state.currentY1 * renderH - cropOffsetY
                        val right = state.currentX2 * renderW - cropOffsetX
                        val bottom = state.currentY2 * renderH - cropOffsetY
                        val boxWidth = right - left
                        val boxHeight = bottom - top
                        if (boxWidth < 2f || boxHeight < 2f) continue

                        val isRecognized = state.status == "recognized"
                            && !state.name.isNullOrEmpty() && state.name != "Unknown"
                        val boxColor = if (isRecognized) {
                            Color(0xFF4CAF50).copy(alpha = alpha)
                        } else {
                            Color(0xFFFF9800).copy(alpha = alpha)
                        }

                        drawRect(
                            color = boxColor,
                            topLeft = Offset(left, top),
                            size = Size(boxWidth, boxHeight),
                            style = Stroke(width = 2.5f)
                        )

                        val label = if (isRecognized) state.name!! else "Unknown"
                        drawNameLabel(textMeasurer, label, left, top, boxColor, alpha)
                    }
                }
            }
    )
}

/** Mutable state for a single tracked face overlay. */
private class TrackOverlayState(
    var targetX1: Float,
    var targetY1: Float,
    var targetX2: Float,
    var targetY2: Float,
    var currentX1: Float,
    var currentY1: Float,
    var currentX2: Float,
    var currentY2: Float,
    var lastUpdateNanos: Long,
    val createdNanos: Long,
    val alpha: Animatable<Float, *>,
    var name: String?,
    var confidence: Float,
    var status: String,
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
