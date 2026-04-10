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
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.sqrt

/**
 * How long (ms) to wait before showing "Unknown" label on a newly-detected face.
 */
private const val UNKNOWN_LABEL_DELAY_MS = 0L

/** Offset to keep backend trackId keys separate from ML Kit faceId keys. */
private const val BACKEND_KEY_OFFSET = 100_000

/** Maximum age (ms) before a track is considered stale and faded out. */
private const val STALE_TRACK_TIMEOUT_MS = 500L

/**
 * Face overlay with persistent identity linking.
 *
 * **Position:** ML Kit (30fps, smooth real-time tracking on phone).
 * **Identity:** Backend tracks via WebSocket (name, status, confidence).
 *
 * A persistent map links each backend trackId → ML Kit faceId. This link is
 * established once (by nearest-center matching) and reused across frames,
 * avoiding per-frame IoU flicker that caused rubber-banding.
 *
 * When ML Kit has the linked face → use ML Kit bbox (30fps smooth).
 * When ML Kit loses the face → fall back to backend bbox.
 * When backend stops sending the track → box disappears immediately.
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

    // Persistent link: backend trackId → ML Kit faceId
    // Survives across recompositions. Updated incrementally, not rebuilt each frame.
    val trackToMlKit = remember { mutableStateMapOf<Int, Int>() }

    // Resolve positions: ML Kit when linked, backend as fallback
    val resolvedTracks = remember(mlKitFaces, backendTracks) {
        resolveWithPersistentLink(backendTracks, mlKitFaces, trackToMlKit)
    }

    // Update animation state
    LaunchedEffect(resolvedTracks) {
        val now = System.currentTimeMillis()
        val activeKeys = resolvedTracks.map { it.key }.toSet()

        // Remove tracks the backend stopped sending — immediate
        val gone = animatedFaces.keys - activeKeys
        gone.forEach { animatedFaces.remove(it) }

        for (rt in resolvedTracks) {
            val existing = animatedFaces[rt.key]
            if (existing != null) {
                // Smooth animate to new position
                // Use faster tween when ML Kit is driving (higher fps)
                val tweenMs = if (rt.fromMlKit) 50 else 100
                coroutineScope.launch { existing.x1.animateTo(rt.x1, tween(tweenMs)) }
                coroutineScope.launch { existing.y1.animateTo(rt.y1, tween(tweenMs)) }
                coroutineScope.launch { existing.x2.animateTo(rt.x2, tween(tweenMs)) }
                coroutineScope.launch { existing.y2.animateTo(rt.y2, tween(tweenMs)) }
                existing.name = rt.name
                existing.confidence = rt.confidence
                if (rt.status == "unknown" && existing.status != "unknown") {
                    existing.unknownSince = now
                } else if (rt.status == "recognized") {
                    existing.unknownSince = 0L
                }
                existing.status = rt.status
                existing.lastUpdatedAt = System.currentTimeMillis()
                if (existing.alpha.value < 1f) {
                    coroutineScope.launch { existing.alpha.animateTo(1f, tween(150)) }
                }
            } else {
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

    // Staleness sweep: fade out and remove tracks not refreshed within timeout
    LaunchedEffect(Unit) {
        while (true) {
            delay(200L)
            val now = System.currentTimeMillis()
            val stale = animatedFaces.entries.filter { (_, state) ->
                (now - state.lastUpdatedAt) > STALE_TRACK_TIMEOUT_MS
            }
            for ((key, state) in stale) {
                launch { state.alpha.animateTo(0f, tween(150)) }
                delay(160L)
                animatedFaces.remove(key)
            }
        }
    }

    Canvas(modifier = modifier.fillMaxSize()) {
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

        val now = System.currentTimeMillis()

        for ((_, state) in animatedFaces) {
            val alpha = state.alpha.value
            if (alpha < 0.01f) continue
            if (state.status == "pending") continue

            val left = state.x1.value * renderW - cropOffsetX
            val top = state.y1.value * renderH - cropOffsetY
            val right = state.x2.value * renderW - cropOffsetX
            val bottom = state.y2.value * renderH - cropOffsetY
            val boxWidth = right - left
            val boxHeight = bottom - top
            if (boxWidth < 2f || boxHeight < 2f) continue

            val boxColor = when (state.status) {
                "recognized" -> Color(0xFF4CAF50)
                else -> Color(0xFFFF9800)
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
                drawNameLabel(textMeasurer, label, left, top, boxWidth, boxColor, alpha)
            }
        }
    }
}

// --- Persistent link resolution ---

private data class ResolvedTrack(
    val key: Int,
    val x1: Float, val y1: Float, val x2: Float, val y2: Float,
    val name: String?,
    val confidence: Float,
    val status: String,
    val fromMlKit: Boolean,
)

/**
 * For each backend track with identity, find its position:
 * 1. If we have a persistent link to an ML Kit faceId AND that face is present → use ML Kit bbox.
 * 2. If no link exists, find the nearest ML Kit face by center distance and create the link.
 * 3. If ML Kit has no matching face at all → fall back to backend bbox.
 *
 * The [trackToMlKit] map is mutated in place to maintain links across frames.
 */
private fun resolveWithPersistentLink(
    backendTracks: List<TrackInfo>,
    mlKitFaces: List<MlKitFace>,
    trackToMlKit: MutableMap<Int, Int>,
): List<ResolvedTrack> {
    // Index ML Kit faces by faceId for O(1) lookup
    val mlKitById = mutableMapOf<Int, MlKitFace>()
    for (face in mlKitFaces) {
        val id = face.faceId ?: continue
        mlKitById[id] = face
    }

    // Track which ML Kit faceIds are claimed this frame
    val claimedMlKit = mutableSetOf<Int>()

    // Clean up stale links: remove any trackId not in current backend tracks
    val activeTrackIds = backendTracks.map { it.trackId }.toSet()
    trackToMlKit.keys.removeAll { it !in activeTrackIds }

    val result = mutableListOf<ResolvedTrack>()

    for (track in backendTracks) {
        if (track.bbox.size < 4) continue
        if (track.status != "recognized" && track.status != "unknown") continue

        val trackCx = (track.bbox[0] + track.bbox[2]) / 2f
        val trackCy = (track.bbox[1] + track.bbox[3]) / 2f

        // Step 1: Check existing persistent link
        val linkedFaceId = trackToMlKit[track.trackId]
        val linkedFace = if (linkedFaceId != null) mlKitById[linkedFaceId] else null

        if (linkedFace != null && linkedFaceId !in claimedMlKit) {
            // Link is alive — use ML Kit position
            claimedMlKit.add(linkedFaceId!!)
            result.add(ResolvedTrack(
                key = track.trackId + BACKEND_KEY_OFFSET,
                x1 = linkedFace.x1, y1 = linkedFace.y1,
                x2 = linkedFace.x2, y2 = linkedFace.y2,
                name = track.name, confidence = track.confidence,
                status = track.status, fromMlKit = true,
            ))
            continue
        }

        // Step 2: Link is broken or doesn't exist — find nearest unclaimed ML Kit face
        var bestFace: MlKitFace? = null
        var bestFaceId: Int? = null
        var bestDist = Float.MAX_VALUE

        for ((faceId, face) in mlKitById) {
            if (faceId in claimedMlKit) continue
            val faceCx = (face.x1 + face.x2) / 2f
            val faceCy = (face.y1 + face.y2) / 2f
            val dx = trackCx - faceCx
            val dy = trackCy - faceCy
            val dist = sqrt(dx * dx + dy * dy)
            // Max distance threshold: 20% of frame diagonal (generous for cross-system matching)
            if (dist < bestDist && dist < 0.2f) {
                bestDist = dist
                bestFace = face
                bestFaceId = faceId
            }
        }

        if (bestFace != null && bestFaceId != null) {
            // Create new persistent link
            trackToMlKit[track.trackId] = bestFaceId
            claimedMlKit.add(bestFaceId)
            result.add(ResolvedTrack(
                key = track.trackId + BACKEND_KEY_OFFSET,
                x1 = bestFace.x1, y1 = bestFace.y1,
                x2 = bestFace.x2, y2 = bestFace.y2,
                name = track.name, confidence = track.confidence,
                status = track.status, fromMlKit = true,
            ))
        } else {
            // No ML Kit face found — fall back to backend bbox
            trackToMlKit.remove(track.trackId)
            result.add(ResolvedTrack(
                key = track.trackId + BACKEND_KEY_OFFSET,
                x1 = track.bbox[0], y1 = track.bbox[1],
                x2 = track.bbox[2], y2 = track.bbox[3],
                name = track.name, confidence = track.confidence,
                status = track.status, fromMlKit = false,
            ))
        }
    }

    return result
}

// --- Drawing helpers ---

private fun DrawScope.drawNameLabel(
    textMeasurer: TextMeasurer,
    label: String,
    x: Float, y: Float,
    boxWidth: Float,
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
    var lastUpdatedAt: Long = System.currentTimeMillis(),
)
