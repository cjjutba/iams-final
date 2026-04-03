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
import com.iams.app.webrtc.MlKitFace
import kotlinx.coroutines.launch

/**
 * How long (ms) to wait before showing "Unknown" label on a newly-detected face.
 * Prevents a single bad frame from instantly labeling a registered student as "Unknown".
 */
private const val UNKNOWN_LABEL_DELAY_MS = 2000L

/** Offset added to backend trackId so it never collides with ML Kit faceId. */
private const val BACKEND_KEY_OFFSET = 100_000

/**
 * Backend-track-centric face overlay.
 *
 * Rendering is driven entirely by backend tracks (via WebSocket frame_update).
 * Each backend track has a stable trackId that persists across frames, enabling
 * smooth animated transitions as the face moves.
 *
 * ML Kit faces are used as an optional position refinement: if an ML Kit face
 * overlaps a backend track (IoU ≥ threshold), we use the ML Kit bbox for that
 * frame since ML Kit runs at higher FPS. Otherwise we use the backend bbox.
 *
 * Key behaviors:
 * - Only "recognized" and "unknown" (after delay) tracks are rendered.
 * - Green box + name for recognized faces.
 * - Orange box + "Unknown" for unknown faces (after delay).
 * - Boxes disappear immediately when the backend stops sending the track.
 * - Smooth animated transitions between frames using backend trackId as stable key.
 */
@Composable
fun HybridFaceOverlay(
    mlKitFaces: List<MlKitFace>,
    backendTracks: List<TrackInfo>,
    modifier: Modifier = Modifier,
    videoFrameWidth: Int = 0,
    videoFrameHeight: Int = 0
) {
    val textMeasurer = rememberTextMeasurer()
    val animatedFaces = remember { mutableStateMapOf<Int, AnimatedFaceState>() }
    val coroutineScope = rememberCoroutineScope()

    // Build the list of tracks to render, with optional ML Kit position refinement
    val resolvedTracks = remember(mlKitFaces, backendTracks) {
        resolveTracksWithMlKit(mlKitFaces, backendTracks)
    }

    // Update animation state from resolved tracks
    LaunchedEffect(resolvedTracks) {
        val now = System.currentTimeMillis()
        val activeKeys = resolvedTracks.map { it.key }.toSet()

        // Remove tracks no longer present — immediate removal, no grace period
        val gone = animatedFaces.keys - activeKeys
        gone.forEach { animatedFaces.remove(it) }

        // Update or create animated state for each active track
        for (rt in resolvedTracks) {
            val existing = animatedFaces[rt.key]
            if (existing != null) {
                // Animate to new position (smooth tracking)
                coroutineScope.launch { existing.x1.animateTo(rt.x1, tween(100)) }
                coroutineScope.launch { existing.y1.animateTo(rt.y1, tween(100)) }
                coroutineScope.launch { existing.x2.animateTo(rt.x2, tween(100)) }
                coroutineScope.launch { existing.y2.animateTo(rt.y2, tween(100)) }
                existing.name = rt.name
                existing.confidence = rt.confidence
                if (rt.status == "unknown" && existing.status != "unknown") {
                    existing.unknownSince = now
                } else if (rt.status == "recognized") {
                    existing.unknownSince = 0L
                }
                existing.status = rt.status
                if (existing.alpha.value < 1f) {
                    coroutineScope.launch { existing.alpha.animateTo(1f, tween(150)) }
                }
            } else {
                // New track — create with current position, fade in
                val state = AnimatedFaceState(
                    x1 = Animatable(rt.x1),
                    y1 = Animatable(rt.y1),
                    x2 = Animatable(rt.x2),
                    y2 = Animatable(rt.y2),
                    alpha = Animatable(0f),
                    name = rt.name,
                    confidence = rt.confidence,
                    status = rt.status,
                    unknownSince = if (rt.status == "unknown") now else 0L,
                )
                animatedFaces[rt.key] = state
                coroutineScope.launch { state.alpha.animateTo(1f, tween(200)) }
            }
        }
    }

    Canvas(modifier = modifier.fillMaxSize()) {
        val canvasW = size.width
        val canvasH = size.height

        // Compute coordinate mapping for SCALE_ASPECT_FILL cropping.
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

        val now = System.currentTimeMillis()

        for ((_, state) in animatedFaces) {
            val alpha = state.alpha.value
            if (alpha < 0.01f) continue

            // Skip pending (shouldn't happen, but safety)
            if (state.status == "pending") continue

            // For unknown: only show after delay
            if (state.status == "unknown") {
                if (state.unknownSince <= 0L || (now - state.unknownSince) < UNKNOWN_LABEL_DELAY_MS) continue
            }

            // Map normalized 0-1 coords to canvas
            val left = state.x1.value * renderW - cropOffsetX
            val top = state.y1.value * renderH - cropOffsetY
            val right = state.x2.value * renderW - cropOffsetX
            val bottom = state.y2.value * renderH - cropOffsetY
            val boxWidth = right - left
            val boxHeight = bottom - top

            if (boxWidth < 2f || boxHeight < 2f) continue

            val boxColor = when (state.status) {
                "recognized" -> Color(0xFF4CAF50)  // Green
                else -> Color(0xFFFF9800)          // Orange
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
                drawNameLabel(
                    textMeasurer = textMeasurer,
                    label = label,
                    x = left,
                    y = top,
                    boxWidth = boxWidth,
                    color = boxColor,
                    alpha = alpha,
                )
            }
        }
    }
}

// --- Track resolution ---

private data class ResolvedTrack(
    val key: Int,          // Stable key for animation (backend trackId + offset)
    val x1: Float,
    val y1: Float,
    val x2: Float,
    val y2: Float,
    val name: String?,
    val confidence: Float,
    val status: String,
)

/**
 * Resolves backend tracks into renderable entries.
 * Uses ML Kit bbox as position source when IoU matches, otherwise backend bbox.
 * Only includes tracks with "recognized" or "unknown" status.
 */
private fun resolveTracksWithMlKit(
    mlKitFaces: List<MlKitFace>,
    backendTracks: List<TrackInfo>,
    iouThreshold: Float = 0.15f
): List<ResolvedTrack> {
    return backendTracks.mapNotNull { track ->
        if (track.bbox.size < 4) return@mapNotNull null
        if (track.status != "recognized" && track.status != "unknown") return@mapNotNull null

        val trackBox = floatArrayOf(track.bbox[0], track.bbox[1], track.bbox[2], track.bbox[3])

        // Try to find a matching ML Kit face for smoother position
        var bestMlKit: MlKitFace? = null
        var bestIou = 0f
        for (face in mlKitFaces) {
            val faceBox = floatArrayOf(face.x1, face.y1, face.x2, face.y2)
            val iou = computeIoU(trackBox, faceBox)
            if (iou > bestIou && iou >= iouThreshold) {
                bestIou = iou
                bestMlKit = face
            }
        }

        // Use ML Kit position if matched (higher fps), otherwise backend position
        val src = bestMlKit
        ResolvedTrack(
            key = track.trackId + BACKEND_KEY_OFFSET,
            x1 = src?.x1 ?: track.bbox[0],
            y1 = src?.y1 ?: track.bbox[1],
            x2 = src?.x2 ?: track.bbox[2],
            y2 = src?.y2 ?: track.bbox[3],
            name = track.name,
            confidence = track.confidence,
            status = track.status,
        )
    }
}

private fun computeIoU(a: FloatArray, b: FloatArray): Float {
    val interX1 = maxOf(a[0], b[0])
    val interY1 = maxOf(a[1], b[1])
    val interX2 = minOf(a[2], b[2])
    val interY2 = minOf(a[3], b[3])

    val interW = maxOf(0f, interX2 - interX1)
    val interH = maxOf(0f, interY2 - interY1)
    val interArea = interW * interH

    val areaA = (a[2] - a[0]) * (a[3] - a[1])
    val areaB = (b[2] - b[0]) * (b[3] - b[1])
    val unionArea = areaA + areaB - interArea

    return if (unionArea > 0f) interArea / unionArea else 0f
}

// --- Drawing helpers ---

private fun DrawScope.drawNameLabel(
    textMeasurer: TextMeasurer,
    label: String,
    x: Float,
    y: Float,
    boxWidth: Float,
    color: Color,
    alpha: Float,
) {
    val textResult = textMeasurer.measure(
        text = AnnotatedString(label),
        style = TextStyle(
            color = Color.White.copy(alpha = alpha),
            fontSize = 11.sp,
        )
    )

    val labelPadH = 6f
    val labelPadV = 3f
    val labelWidth = textResult.size.width + labelPadH * 2
    val labelHeight = textResult.size.height + labelPadV * 2

    drawRect(
        color = color.copy(alpha = 0.8f * alpha),
        topLeft = Offset(x, y - labelHeight),
        size = Size(labelWidth, labelHeight)
    )

    drawText(
        textLayoutResult = textResult,
        topLeft = Offset(x + labelPadH, y - labelHeight + labelPadV)
    )
}

/** Mutable state for animating a single face's bbox and opacity. */
private class AnimatedFaceState(
    val x1: Animatable<Float, *>,
    val y1: Animatable<Float, *>,
    val x2: Animatable<Float, *>,
    val y2: Animatable<Float, *>,
    val alpha: Animatable<Float, *>,
    var name: String?,
    var confidence: Float,
    var status: String,
    var unknownSince: Long = 0L,
)
