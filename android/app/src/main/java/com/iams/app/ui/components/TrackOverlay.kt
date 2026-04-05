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

/**
 * Overlay composable that draws bounding boxes and names from backend track data.
 *
 * Replaces FaceOverlay.kt (IoU-based matching). Now the backend provides persistent
 * track IDs, so we key animations by track_id for smooth interpolation.
 *
 * - Green box + name for "recognized" tracks
 * - Yellow box + "Unknown" for "unknown" tracks
 * - Faded gray for "pending" tracks
 * - Smooth lerp animation between WebSocket updates
 */
@Composable
fun TrackOverlay(
    tracks: List<TrackInfo>,
    modifier: Modifier = Modifier
) {
    val textMeasurer = rememberTextMeasurer()

    // Animated positions keyed by track_id
    val animatedTracks = remember { mutableStateMapOf<Int, AnimatedTrackState>() }
    val coroutineScope = rememberCoroutineScope()

    // Update animations when tracks change
    LaunchedEffect(tracks) {
        val currentIds = tracks.map { it.trackId }.toSet()

        // Remove tracks no longer present
        val removed = animatedTracks.keys - currentIds
        removed.forEach { animatedTracks.remove(it) }

        // Update or create animated state
        for (track in tracks) {
            val existing = animatedTracks[track.trackId]
            if (existing != null) {
                // Animate to new position
                coroutineScope.launch { existing.x1.animateTo(track.bbox[0], tween(80)) }
                coroutineScope.launch { existing.y1.animateTo(track.bbox[1], tween(80)) }
                coroutineScope.launch { existing.x2.animateTo(track.bbox[2], tween(80)) }
                coroutineScope.launch { existing.y2.animateTo(track.bbox[3], tween(80)) }
                existing.name = track.name
                existing.confidence = track.confidence
                existing.status = track.status
                // Animate opacity to full
                if (existing.alpha.value < 1f) {
                    coroutineScope.launch { existing.alpha.animateTo(1f, tween(200)) }
                }
            } else {
                // New track — fade in
                val state = AnimatedTrackState(
                    x1 = Animatable(track.bbox[0]),
                    y1 = Animatable(track.bbox[1]),
                    x2 = Animatable(track.bbox[2]),
                    y2 = Animatable(track.bbox[3]),
                    alpha = Animatable(0f),
                    name = track.name,
                    confidence = track.confidence,
                    status = track.status,
                )
                animatedTracks[track.trackId] = state
                coroutineScope.launch { state.alpha.animateTo(1f, tween(300)) }
            }
        }
    }

    Canvas(modifier = modifier.fillMaxSize()) {
        val w = size.width
        val h = size.height

        for ((_, state) in animatedTracks) {
            val alpha = state.alpha.value
            if (alpha < 0.01f) continue

            val left = state.x1.value * w
            val top = state.y1.value * h
            val right = state.x2.value * w
            val bottom = state.y2.value * h
            val boxWidth = right - left
            val boxHeight = bottom - top

            if (boxWidth < 2f || boxHeight < 2f) continue

            val boxColor = when (state.status) {
                "recognized" -> Color(0xFF4CAF50)  // Green
                "unknown" -> Color(0xFFFF9800)     // Orange/Yellow
                else -> Color(0xFF9E9E9E)          // Gray for pending
            }.copy(alpha = alpha)

            // Draw bounding box
            drawRect(
                color = boxColor,
                topLeft = Offset(left, top),
                size = Size(boxWidth, boxHeight),
                style = Stroke(width = 2.5f)
            )

            // Draw name label
            val label = state.name ?: if (state.status == "unknown") "Unknown" else ""
            if (label.isNotEmpty()) {
                drawNameLabel(
                    textMeasurer = textMeasurer,
                    label = label,
                    confidence = state.confidence,
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

private fun DrawScope.drawNameLabel(
    textMeasurer: TextMeasurer,
    label: String,
    confidence: Float,
    x: Float,
    y: Float,
    boxWidth: Float,
    color: Color,
    alpha: Float,
) {
    val displayText = if (confidence > 0.01f) {
        "$label ${(confidence * 100).toInt()}%"
    } else {
        label
    }

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

/** Mutable state for animating a single track's bbox and opacity. */
private class AnimatedTrackState(
    val x1: Animatable<Float, *>,
    val y1: Animatable<Float, *>,
    val x2: Animatable<Float, *>,
    val y2: Animatable<Float, *>,
    val alpha: Animatable<Float, *>,
    var name: String?,
    var confidence: Float,
    var status: String,
)
