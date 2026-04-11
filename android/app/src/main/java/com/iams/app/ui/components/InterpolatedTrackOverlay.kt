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
import kotlin.math.min

/** Stale timeout: fade out if no update for this long. */
private const val STALE_TIMEOUT_NS = 500_000_000L // 500ms

/** Maximum extrapolation time to prevent runaway drift. */
private const val MAX_EXTRAPOLATION_S = 0.3

/**
 * Backend-authoritative face overlay with velocity-based interpolation.
 *
 * Unlike HybridFaceOverlay, this does NOT use ML Kit for positioning.
 * All positions and identities come from the backend via WebSocket.
 * Velocity data enables smooth interpolation between 15fps backend
 * updates, rendering at the display's native refresh rate (~60fps).
 *
 * This eliminates name swaps caused by matching two independent
 * detection systems (backend SCRFD vs phone ML Kit).
 */
@Composable
fun InterpolatedTrackOverlay(
    tracks: List<TrackInfo>,
    modifier: Modifier = Modifier,
    videoFrameWidth: Int = 0,
    videoFrameHeight: Int = 0
) {
    val textMeasurer = rememberTextMeasurer()
    val trackStates = remember { mutableStateMapOf<Int, InterpolatedTrackState>() }
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
            val vel = track.velocity ?: listOf(0f, 0f, 0f, 0f)
            val vx = vel.getOrElse(0) { 0f }
            val vy = vel.getOrElse(1) { 0f }
            val vw = vel.getOrElse(2) { 0f }
            val vh = vel.getOrElse(3) { 0f }

            val existing = trackStates[track.trackId]
            if (existing != null) {
                // Update existing track with new backend data
                existing.targetX1 = track.bbox[0]
                existing.targetY1 = track.bbox[1]
                existing.targetX2 = track.bbox[2]
                existing.targetY2 = track.bbox[3]
                existing.vx = vx
                existing.vy = vy
                existing.vw = vw
                existing.vh = vh
                existing.lastUpdateNanos = now
                existing.name = track.name
                existing.confidence = track.confidence
                existing.status = track.status
                existing.isAlive = true
                if (existing.alpha.value < 1f) {
                    coroutineScope.launch { existing.alpha.animateTo(1f, tween(150)) }
                }
            } else {
                // New track — create state and fade in
                val state = InterpolatedTrackState(
                    targetX1 = track.bbox[0],
                    targetY1 = track.bbox[1],
                    targetX2 = track.bbox[2],
                    targetY2 = track.bbox[3],
                    vx = vx, vy = vy, vw = vw, vh = vh,
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

        // Compute aspect-fit crop offsets (same as HybridFaceOverlay)
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

            // Interpolate position using velocity between backend updates
            val dtSeconds = min(
                (now - state.lastUpdateNanos).toDouble() / 1_000_000_000.0,
                MAX_EXTRAPOLATION_S
            ).toFloat()

            // Stale check: if no update for >500ms, skip rendering.
            // This handles the case where WebSocket stops entirely —
            // LaunchedEffect(tracks) won't fire, so we must check here.
            val age = now - state.lastUpdateNanos
            if (age > STALE_TIMEOUT_NS) {
                continue
            }

            // Interpolate in center+size space
            val baseCx = (state.targetX1 + state.targetX2) / 2f
            val baseCy = (state.targetY1 + state.targetY2) / 2f
            val baseW = state.targetX2 - state.targetX1
            val baseH = state.targetY2 - state.targetY1

            val cx = (baseCx + state.vx * dtSeconds).coerceIn(0f, 1f)
            val cy = (baseCy + state.vy * dtSeconds).coerceIn(0f, 1f)
            val w = (baseW + state.vw * dtSeconds).coerceAtLeast(0.01f)
            val h = (baseH + state.vh * dtSeconds).coerceAtLeast(0.01f)

            // Convert back to corners
            val x1 = (cx - w / 2f).coerceIn(0f, 1f)
            val y1 = (cy - h / 2f).coerceIn(0f, 1f)
            val x2 = (cx + w / 2f).coerceIn(0f, 1f)
            val y2 = (cy + h / 2f).coerceIn(0f, 1f)

            // Map to canvas coordinates
            val left = x1 * renderW - cropOffsetX
            val top = y1 * renderH - cropOffsetY
            val right = x2 * renderW - cropOffsetX
            val bottom = y2 * renderH - cropOffsetY
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

/** Mutable state for a single interpolated track. */
private class InterpolatedTrackState(
    var targetX1: Float,
    var targetY1: Float,
    var targetX2: Float,
    var targetY2: Float,
    var vx: Float,
    var vy: Float,
    var vw: Float,
    var vh: Float,
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
