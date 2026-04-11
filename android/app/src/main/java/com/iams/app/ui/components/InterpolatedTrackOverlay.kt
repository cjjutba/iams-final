package com.iams.app.ui.components

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.*
import androidx.compose.ui.unit.sp
import com.iams.app.data.model.TrackInfo
import kotlinx.coroutines.launch

/** Stale timeout: fade out if no update for this long. */
private const val STALE_TIMEOUT_NS = 500_000_000L // 500ms

/**
 * Lerp factor per frame (at 60fps). 0.35 = move 35% toward target each frame.
 * Gives smooth motion without drift. At 60fps, reaches 95% of target in ~5 frames (~83ms).
 */
private const val LERP_FACTOR = 0.35f

/**
 * Backend-authoritative face overlay with smooth lerp positioning.
 *
 * All positions and identities come from the backend via WebSocket.
 * Smooth lerp interpolation between backend keyframes (10-15fps)
 * rendered at the display's native refresh rate (~60fps).
 * No velocity extrapolation — avoids drift while staying smooth.
 */
@Composable
fun InterpolatedTrackOverlay(
    tracks: List<TrackInfo>,
    modifier: Modifier = Modifier,
    videoFrameWidth: Int = 0,
    videoFrameHeight: Int = 0
) {
    val textMeasurer = rememberTextMeasurer()
    val trackStates = remember { mutableStateMapOf<Int, TrackOverlayState>() }
    val coroutineScope = rememberCoroutineScope()

    // Trigger continuous recomposition at display refresh rate
    var frameNanos by remember { mutableLongStateOf(0L) }
    LaunchedEffect(Unit) {
        while (true) {
            withFrameNanos { nanos -> frameNanos = nanos }
        }
    }

    // Update track states when new WebSocket data arrives
    LaunchedEffect(tracks) {
        val now = System.nanoTime()
        val activeIds = tracks.map { it.trackId }.toSet()

        // Mark disappeared tracks for fade-out
        for ((id, state) in trackStates) {
            if (id !in activeIds && state.isAlive) {
                state.isAlive = false
                state.deathTimeNanos = now
                coroutineScope.launch { state.alpha.animateTo(0f, tween(200)) }
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
                // Update target — lerp will smoothly move toward it each frame
                existing.targetX1 = track.bbox[0]
                existing.targetY1 = track.bbox[1]
                existing.targetX2 = track.bbox[2]
                existing.targetY2 = track.bbox[3]
                existing.lastUpdateNanos = now
                existing.name = track.name
                existing.confidence = track.confidence
                existing.status = track.status
                existing.isAlive = true
                if (existing.alpha.value < 1f) {
                    coroutineScope.launch { existing.alpha.animateTo(1f, tween(150)) }
                }
            } else {
                // New track — snap to initial position and fade in
                val state = TrackOverlayState(
                    targetX1 = track.bbox[0],
                    targetY1 = track.bbox[1],
                    targetX2 = track.bbox[2],
                    targetY2 = track.bbox[3],
                    // Start current position at target (no lerp on first frame)
                    currentX1 = track.bbox[0],
                    currentY1 = track.bbox[1],
                    currentX2 = track.bbox[2],
                    currentY2 = track.bbox[3],
                    lastUpdateNanos = now,
                    alpha = Animatable(0f),
                    name = track.name,
                    confidence = track.confidence,
                    status = track.status,
                )
                trackStates[track.trackId] = state
                coroutineScope.launch { state.alpha.animateTo(1f, tween(200)) }
            }
        }
    }

    Canvas(modifier = modifier.fillMaxSize()) {
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

        val now = frameNanos.takeIf { it > 0L } ?: System.nanoTime()

        for ((_, state) in trackStates) {
            val alpha = state.alpha.value
            if (alpha < 0.01f) continue
            if (state.status == "pending") continue

            // Stale check: skip rendering if no backend update for >500ms
            val age = now - state.lastUpdateNanos
            if (age > STALE_TIMEOUT_NS) {
                continue
            }

            // Smooth lerp: move current position toward target each frame.
            // At 60fps with LERP_FACTOR=0.35, reaches 95% of target in ~83ms.
            // Accurate (always converges to backend position) and smooth (no jitter).
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

            val boxColor = when (state.status) {
                "recognized" -> Color(0xFF4CAF50)
                "unknown" -> Color(0xFFFF9800)
                else -> Color(0xFF9E9E9E)
            }.copy(alpha = alpha)

            drawRect(
                color = boxColor,
                topLeft = Offset(left, top),
                size = Size(boxWidth, boxHeight),
                style = Stroke(width = 2.5f)
            )

            val label = when (state.status) {
                "recognized" -> state.name ?: ""
                else -> "Unknown"
            }
            if (label.isNotEmpty()) {
                drawNameLabel(textMeasurer, label, left, top, boxColor, alpha)
            }
        }
    }
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
    val alpha: Animatable<Float, *>,
    var name: String?,
    var confidence: Float,
    var status: String,
    var isAlive: Boolean = true,
    var deathTimeNanos: Long = 0L,
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
