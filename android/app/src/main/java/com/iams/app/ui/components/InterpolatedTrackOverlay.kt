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

/** Stale timeout: stop rendering if no backend update for this long. */
private const val STALE_TIMEOUT_NS = 500_000_000L // 500ms

/**
 * Backend-authoritative face overlay with snap positioning.
 *
 * All positions and identities come from the backend via WebSocket.
 * Boxes snap directly to the backend-reported position — no interpolation,
 * no lerp, no velocity extrapolation. This guarantees the box is always
 * exactly where SCRFD detected the face, with zero drift or lag.
 *
 * At 10-15fps backend updates, position jumps are small enough (~3-5px)
 * that snapping looks stable to the eye.
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
                // Snap to new backend position
                existing.x1 = track.bbox[0]
                existing.y1 = track.bbox[1]
                existing.x2 = track.bbox[2]
                existing.y2 = track.bbox[3]
                existing.lastUpdateNanos = now
                existing.name = track.name
                existing.confidence = track.confidence
                existing.status = track.status
                existing.isAlive = true
                if (existing.alpha.value < 1f) {
                    coroutineScope.launch { existing.alpha.animateTo(1f, tween(150)) }
                }
            } else {
                // New track — create and fade in
                val state = TrackOverlayState(
                    x1 = track.bbox[0],
                    y1 = track.bbox[1],
                    x2 = track.bbox[2],
                    y2 = track.bbox[3],
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

        val now = System.nanoTime()

        for ((_, state) in trackStates) {
            val alpha = state.alpha.value
            if (alpha < 0.01f) continue
            // Skip pending tracks (not yet processed)
            if (state.status == "pending") continue

            // Stale check: stop rendering if no backend update for >500ms
            if (now - state.lastUpdateNanos > STALE_TIMEOUT_NS) {
                continue
            }

            // Map normalized bbox directly to canvas coordinates
            val left = state.x1 * renderW - cropOffsetX
            val top = state.y1 * renderH - cropOffsetY
            val right = state.x2 * renderW - cropOffsetX
            val bottom = state.y2 * renderH - cropOffsetY
            val boxWidth = right - left
            val boxHeight = bottom - top
            if (boxWidth < 2f || boxHeight < 2f) continue

            val isRecognized = state.status == "recognized" && !state.name.isNullOrEmpty() && state.name != "Unknown"
            val boxColor = if (isRecognized) {
                Color(0xFF4CAF50).copy(alpha = alpha) // Green for recognized
            } else {
                Color(0xFFFF9800).copy(alpha = alpha) // Orange/yellow for unknown
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

/** Mutable state for a single tracked face overlay. */
private class TrackOverlayState(
    var x1: Float,
    var y1: Float,
    var x2: Float,
    var y2: Float,
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
