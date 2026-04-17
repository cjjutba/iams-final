package com.iams.app.ui.components

import android.util.Log
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import com.iams.app.webrtc.WhepClient
import com.iams.app.webrtc.WhepConnectionState
import java.util.concurrent.atomic.AtomicBoolean
import org.webrtc.RendererCommon
import org.webrtc.SurfaceViewRenderer
import org.webrtc.VideoFrame
import org.webrtc.VideoSink
import org.webrtc.VideoTrack

private const val TAG = "NativeWebRtcPlayer"

/**
 * VideoSink wrapper that fires a callback on the first frame rendered.
 *
 * Used to synchronize the bounding-box overlay with actual video rendering
 * so detections don't appear on a black screen during WebRTC negotiation.
 * The callback fires exactly once, on the first real frame.
 */
private class FirstFrameDetector(
    private val onFirstFrame: () -> Unit
) : VideoSink {
    private val signaled = AtomicBoolean(false)

    override fun onFrame(frame: VideoFrame) {
        // Fire callback on first frame only (atomic CAS — safe from any thread)
        if (signaled.compareAndSet(false, true)) {
            onFirstFrame()
        }
    }
}

/**
 * Native WebRTC video player using WHEP signaling with mediamtx.
 *
 * Uses SurfaceViewRenderer for reliable hardware-accelerated rendering.
 *
 * @param onVideoReady Called exactly once when the first video frame is rendered.
 *                     Use this to synchronize overlays (bounding boxes, etc.)
 *                     with actual video display.
 */
@Composable
fun NativeWebRtcVideoPlayer(
    whepUrl: String,
    modifier: Modifier = Modifier,
    onError: ((String) -> Unit)? = null,
    additionalSink: VideoSink? = null,
    onVideoReady: () -> Unit = {}
) {
    val context = LocalContext.current
    val client = remember(whepUrl) {
        WhepClient(context.applicationContext, whepUrl)
    }

    val videoTrack by client.videoTrack.collectAsState()
    val connectionState by client.state.collectAsState()

    // Stable first-frame detector tied to this whepUrl. Rebuilt if whepUrl changes.
    val firstFrameDetector = remember(whepUrl) {
        FirstFrameDetector {
            Log.i(TAG, "First video frame rendered")
            onVideoReady()
        }
    }

    // Start connection
    LaunchedEffect(client) {
        client.connect()
    }

    // Report errors
    LaunchedEffect(connectionState) {
        if (connectionState is WhepConnectionState.Failed) {
            val reason = (connectionState as WhepConnectionState.Failed).reason
            Log.e(TAG, "Connection failed: $reason")
            onError?.invoke(reason)
        }
    }

    // Cleanup
    DisposableEffect(client) {
        onDispose {
            Log.i(TAG, "Releasing WhepClient")
            client.release()
        }
    }

    // Track ref for sink management
    val currentTrack = remember { mutableStateOf<VideoTrack?>(null) }
    val rendererRef = remember { mutableStateOf<SurfaceViewRenderer?>(null) }

    // Manage sinks: renderer + first-frame detector + optional additional sink
    LaunchedEffect(videoTrack, additionalSink) {
        val renderer = rendererRef.value
        val oldTrack = currentTrack.value
        val newTrack = videoTrack

        if (oldTrack != newTrack) {
            if (oldTrack != null) {
                if (renderer != null) {
                    try { oldTrack.removeSink(renderer) } catch (_: Exception) {}
                }
                try { oldTrack.removeSink(firstFrameDetector) } catch (_: Exception) {}
                additionalSink?.let { try { oldTrack.removeSink(it) } catch (_: Exception) {} }
            }
            if (newTrack != null) {
                if (renderer != null) {
                    newTrack.addSink(renderer)
                }
                newTrack.addSink(firstFrameDetector)
                additionalSink?.let { newTrack.addSink(it) }
                Log.i(TAG, "Video sinks attached (additional=${additionalSink != null})")
            }
            currentTrack.value = newTrack
        }
    }

    Box(modifier = modifier.background(Color.Black)) {
        AndroidView(
            factory = { ctx ->
                SurfaceViewRenderer(ctx).apply {
                    // Default z-order: SurfaceView renders behind the View hierarchy,
                    // allowing Compose Canvas overlays (bounding boxes) to draw on top.
                    setEnableHardwareScaler(false)
                    setScalingType(RendererCommon.ScalingType.SCALE_ASPECT_FIT)
                    init(client.eglBase.eglBaseContext, null)
                    rendererRef.value = this

                    // Attach track if already available
                    videoTrack?.let { track ->
                        track.addSink(this)
                        track.addSink(firstFrameDetector)
                        additionalSink?.let { track.addSink(it) }
                    }
                    currentTrack.value = videoTrack
                }
            },
            modifier = Modifier.matchParentSize(),
            onRelease = { renderer ->
                currentTrack.value?.let { track ->
                    track.removeSink(renderer)
                    try { track.removeSink(firstFrameDetector) } catch (_: Exception) {}
                    additionalSink?.let { try { track.removeSink(it) } catch (_: Exception) {} }
                }
                currentTrack.value = null
                rendererRef.value = null
                renderer.release()
            }
        )
    }
}
