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
 * Correction lerp factor: how fast the current position snaps to the
 * extrapolated target when a new WebSocket update corrects the prediction.
 * 0.80 = snap 80% of the correction per frame at 60fps → reaches 95% in ~1 frame.
 * High value is fine because extrapolation handles smooth movement; lerp only
 * corrects prediction errors which should be small and applied instantly.
 */
private const val LERP_FACTOR = 0.80f

/**
 * Backend-authoritative face overlay with velocity extrapolation.
 *
 * All positions and identities come from the backend via WebSocket at ~10fps.
 * Between updates, the overlay uses the backend-provided velocity vector to
 * PREDICT where the face is moving (dead reckoning). When the next WebSocket
 * update arrives, the target is corrected and lerp snaps to it.
 *
 * This eliminates the visible lag where boxes trail behind moving faces.
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
    val trackStates = remember { mutableMapOf<Int, TrackOverlayState>() }
    val coroutineScope = rememberCoroutineScope()

    // Invalidation trigger: incremented to force Canvas redraw without recomposition
    var drawTick by remember { mutableIntStateOf(0) }

    // Drive continuous 60fps rendering
    LaunchedEffect(Unit) {
        while (true) {
            withFrameNanos { _ -> drawTick++ }
        }
    }

    // Update target positions when new WebSocket data arrives (~10fps).
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

            // Extract velocity (center+size space: [vCx, vCy, vW, vH] in normalized units/sec).
            // Convert to corner-space velocity for x1,y1,x2,y2:
            //   x1 = cx - w/2  →  vx1 = vCx - vW/2
            //   y1 = cy - h/2  →  vy1 = vCy - vH/2
            //   x2 = cx + w/2  →  vx2 = vCx + vW/2
            //   y2 = cy + h/2  →  vy2 = vCy + vH/2
            val vel = track.velocity
            val vx1: Float; val vy1: Float; val vx2: Float; val vy2: Float
            if (vel != null && vel.size >= 4) {
                val vCx = vel[0]; val vCy = vel[1]; val vW = vel[2]; val vH = vel[3]
                vx1 = vCx - vW / 2f
                vy1 = vCy - vH / 2f
                vx2 = vCx + vW / 2f
                vy2 = vCy + vH / 2f
            } else {
                vx1 = 0f; vy1 = 0f; vx2 = 0f; vy2 = 0f
            }

            if (existing != null) {
                // Update authoritative target from backend
                existing.targetX1 = track.bbox[0]
                existing.targetY1 = track.bbox[1]
                existing.targetX2 = track.bbox[2]
                existing.targetY2 = track.bbox[3]
                existing.velX1 = vx1
                existing.velY1 = vy1
                existing.velX2 = vx2
                existing.velY2 = vy2
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
                    velX1 = vx1, velY1 = vy1, velX2 = vx2, velY2 = vy2,
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
                    val now = System.nanoTime()

                    for ((_, state) in trackStates) {
                        val alpha = state.alpha.value
                        if (alpha < 0.01f) continue
                        if (state.status == "pending") continue

                        val isRecognizedTrack = state.status == "recognized"
                            && !state.name.isNullOrEmpty() && state.name != "Unknown"
                        val trackAge = now - state.createdNanos
                        if (!isRecognizedTrack && trackAge < 800_000_000L) continue

                        if (now - state.lastUpdateNanos > STALE_TIMEOUT_NS) continue

                        // Dead reckoning: extrapolate target using velocity.
                        // timeSinceUpdate = how long since last WebSocket position update.
                        // Predict where the face IS NOW based on its velocity.
                        val dtSeconds = (now - state.lastUpdateNanos).toFloat() / 1_000_000_000f
                        val extraX1 = state.targetX1 + state.velX1 * dtSeconds
                        val extraY1 = state.targetY1 + state.velY1 * dtSeconds
                        val extraX2 = state.targetX2 + state.velX2 * dtSeconds
                        val extraY2 = state.targetY2 + state.velY2 * dtSeconds

                        // Lerp current position toward extrapolated target.
                        // High lerp factor (0.80) snaps corrections fast since
                        // extrapolation handles smooth movement prediction.
                        state.currentX1 += (extraX1 - state.currentX1) * LERP_FACTOR
                        state.currentY1 += (extraY1 - state.currentY1) * LERP_FACTOR
                        state.currentX2 += (extraX2 - state.currentX2) * LERP_FACTOR
                        state.currentY2 += (extraY2 - state.currentY2) * LERP_FACTOR

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
    // Velocity in corner space (normalized units/second)
    var velX1: Float,
    var velY1: Float,
    var velX2: Float,
    var velY2: Float,
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
