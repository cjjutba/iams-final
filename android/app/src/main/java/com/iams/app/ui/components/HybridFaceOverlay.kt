package com.iams.app.ui.components

import android.util.Log
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

private const val TAG = "HybridFaceOverlay"

/** How long a disappeared face stays visible (ms) before being removed. */
private const val GRACE_PERIOD_MS = 3000L

/**
 * How long (ms) to wait before showing "Unknown" label on a newly-detected face.
 * This prevents a single bad recognition frame from instantly labeling a registered
 * student as "Unknown" while the backend retries recognition.
 */
private const val UNKNOWN_LABEL_DELAY_MS = 2000L

/**
 * Hybrid overlay that combines ML Kit real-time face detection (15-30fps)
 * with backend identity labels from WebSocket.
 *
 * ML Kit provides instant bounding box positions (tracks face movement).
 * Backend provides identity (name, confidence, recognition status) via IoU matching.
 *
 * Key behaviors:
 * - Faces without a backend match yet show a subtle white box (no label).
 * - Only faces the backend explicitly marks "unknown" show "Unknown" label.
 * - Disappeared faces persist for [GRACE_PERIOD_MS] with gradual fade.
 * - Unmatched recognized backend tracks render as fallback when ML Kit loses a face.
 *
 * The overlay accounts for SurfaceViewRenderer's SCALE_ASPECT_FILL cropping
 * by computing the video display rect and mapping normalized coords into it.
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

    // Match ML Kit faces to backend tracks via IoU, plus unmatched backend fallbacks
    val matched = remember(mlKitFaces, backendTracks) {
        matchFaces(mlKitFaces, backendTracks)
    }

    // Update animations when faces change
    LaunchedEffect(matched) {
        val currentIds = matched.map { it.faceKey }.toSet()
        val now = System.currentTimeMillis()

        // For faces no longer present: check grace period instead of removing immediately
        val disappeared = animatedFaces.keys - currentIds
        val expired = mutableSetOf<Int>()
        for (key in disappeared) {
            val state = animatedFaces[key] ?: continue
            if (now - state.lastSeenTime > GRACE_PERIOD_MS) {
                expired.add(key)
            }
            // Otherwise keep it — it's within grace period, will fade in Canvas
        }
        expired.forEach { animatedFaces.remove(it) }

        // Update or create animated state for currently matched faces
        for (match in matched) {
            val newStatus = match.track?.status ?: "pending"
            val existing = animatedFaces[match.faceKey]
            if (existing != null) {
                coroutineScope.launch { existing.x1.animateTo(match.face.x1, tween(50)) }
                coroutineScope.launch { existing.y1.animateTo(match.face.y1, tween(50)) }
                coroutineScope.launch { existing.x2.animateTo(match.face.x2, tween(50)) }
                coroutineScope.launch { existing.y2.animateTo(match.face.y2, tween(50)) }
                existing.name = match.track?.name
                existing.confidence = match.track?.confidence ?: 0f
                // Track when "unknown" status first appears; clear it on recognition
                if (newStatus == "unknown" && existing.status != "unknown") {
                    existing.unknownSince = now
                } else if (newStatus == "recognized") {
                    existing.unknownSince = 0L
                }
                existing.status = newStatus
                existing.lastSeenTime = now
                if (existing.alpha.value < 1f) {
                    coroutineScope.launch { existing.alpha.animateTo(1f, tween(200)) }
                }
            } else {
                val state = AnimatedFaceState(
                    x1 = Animatable(match.face.x1),
                    y1 = Animatable(match.face.y1),
                    x2 = Animatable(match.face.x2),
                    y2 = Animatable(match.face.y2),
                    alpha = Animatable(0f),
                    name = match.track?.name,
                    confidence = match.track?.confidence ?: 0f,
                    status = newStatus,
                    lastSeenTime = now,
                    unknownSince = if (newStatus == "unknown") now else 0L,
                )
                animatedFaces[match.faceKey] = state
                coroutineScope.launch { state.alpha.animateTo(1f, tween(300)) }
            }
        }
    }

    Canvas(modifier = modifier.fillMaxSize()) {
        val canvasW = size.width
        val canvasH = size.height

        // Compute coordinate mapping for SCALE_ASPECT_FILL.
        // The video fills the entire container by cropping overflow edges.
        // ML Kit processes the FULL frame, so we map from full-frame normalized
        // coords to the visible (cropped) portion of the container.
        val cropOffsetX: Float
        val cropOffsetY: Float
        val renderW: Float
        val renderH: Float

        if (videoFrameWidth > 0 && videoFrameHeight > 0) {
            val videoAspect = videoFrameWidth.toFloat() / videoFrameHeight.toFloat()
            val canvasAspect = canvasW / canvasH

            if (videoAspect > canvasAspect) {
                // Video is wider → fills height, crops left/right
                renderH = canvasH
                renderW = canvasH * videoAspect  // wider than canvasW
                cropOffsetX = (renderW - canvasW) / 2f
                cropOffsetY = 0f
            } else {
                // Video is taller → fills width, crops top/bottom
                renderW = canvasW
                renderH = canvasW / videoAspect  // taller than canvasH
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
            val baseAlpha = state.alpha.value
            if (baseAlpha < 0.01f) continue

            // Only render classified faces — no white "pending" boxes.
            // For "unknown" faces, wait until the label delay passes before showing.
            val isUnknownReady = state.status == "unknown" &&
                state.unknownSince > 0L &&
                (now - state.unknownSince) >= UNKNOWN_LABEL_DELAY_MS
            if (state.status == "pending") continue
            if (state.status == "unknown" && !isUnknownReady) continue

            // Compute grace period fade: faces within grace period fade out gradually
            val elapsed = now - state.lastSeenTime
            val graceFade = if (elapsed > 0) {
                (1f - (elapsed.toFloat() / GRACE_PERIOD_MS)).coerceIn(0f, 1f)
            } else {
                1f
            }
            val alpha = baseAlpha * graceFade
            if (alpha < 0.01f) continue

            // Map normalized 0-1 coords: scale to rendered size, then subtract crop offset
            val left = state.x1.value * renderW - cropOffsetX
            val top = state.y1.value * renderH - cropOffsetY
            val right = state.x2.value * renderW - cropOffsetX
            val bottom = state.y2.value * renderH - cropOffsetY
            val boxWidth = right - left
            val boxHeight = bottom - top

            if (boxWidth < 2f || boxHeight < 2f) continue

            // At this point, status is either "recognized" or "unknown" (delay passed).
            val boxColor = when (state.status) {
                "recognized" -> Color(0xFF4CAF50)  // Green
                else -> Color(0xFFFF9800)          // Orange — unknown
            }.copy(alpha = alpha)

            // Draw bounding box
            drawRect(
                color = boxColor,
                topLeft = Offset(left, top),
                size = Size(boxWidth, boxHeight),
                style = Stroke(width = 2.5f)
            )

            // Draw name label
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

// --- IoU matching ---

private data class MatchedFace(
    val face: MlKitFace,
    val faceKey: Int,           // ML Kit faceId or synthetic ID
    val track: TrackInfo?,      // null if no backend match
)

private fun matchFaces(
    mlKitFaces: List<MlKitFace>,
    backendTracks: List<TrackInfo>,
    iouThreshold: Float = 0.3f
): List<MatchedFace> {
    val usedTrackIds = mutableSetOf<Int>()
    var syntheticId = -1

    val result = mlKitFaces.map { face ->
        val faceBox = floatArrayOf(face.x1, face.y1, face.x2, face.y2)

        var bestTrack: TrackInfo? = null
        var bestIou = 0f

        for (track in backendTracks) {
            if (track.trackId in usedTrackIds) continue
            if (track.bbox.size < 4) continue
            val trackBox = floatArrayOf(
                track.bbox[0], track.bbox[1], track.bbox[2], track.bbox[3]
            )
            val iou = computeIoU(faceBox, trackBox)
            if (iou > bestIou && iou >= iouThreshold) {
                bestIou = iou
                bestTrack = track
            }
        }

        if (bestTrack != null) {
            usedTrackIds.add(bestTrack.trackId)
        }

        val key = face.faceId ?: syntheticId--

        MatchedFace(face, key, bestTrack)
    }.toMutableList()

    // Backend-only fallback tracks removed: only render boxes when ML Kit detects
    // a face. This prevents ghost/stale boxes when a face is covered or leaves the
    // frame but the backend's last WebSocket update still contains the track.

    return result
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
    val displayText = label

    val textResult = textMeasurer.measure(
        text = AnnotatedString(displayText),
        style = TextStyle(
            color = Color.White.copy(alpha = alpha),
            fontSize = 11.sp,
        )
    )

    val labelPadH = 6f
    val labelPadV = 3f
    val labelWidth = textResult.size.width + labelPadH * 2
    val labelHeight = textResult.size.height + labelPadV * 2

    // Background behind label
    drawRect(
        color = color.copy(alpha = 0.8f * alpha),
        topLeft = Offset(x, y - labelHeight),
        size = Size(labelWidth, labelHeight)
    )

    // Text
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
    var lastSeenTime: Long,
    /** Timestamp (ms) when status first became "unknown". 0 = never unknown. */
    var unknownSince: Long = 0L,
)
