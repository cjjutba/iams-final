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
import org.webrtc.RendererCommon
import org.webrtc.SurfaceViewRenderer
import org.webrtc.VideoTrack

private const val TAG = "NativeWebRtcPlayer"

/**
 * Native WebRTC video player using WHEP signaling with mediamtx.
 *
 * Drop-in replacement for the old WebView-based WebRtcVideoPlayer.
 * Uses SurfaceViewRenderer for reliable hardware-accelerated rendering.
 */
@Composable
fun NativeWebRtcVideoPlayer(
    whepUrl: String,
    modifier: Modifier = Modifier,
    onError: ((String) -> Unit)? = null
) {
    val context = LocalContext.current
    val client = remember(whepUrl) {
        WhepClient(context.applicationContext, whepUrl)
    }

    val videoTrack by client.videoTrack.collectAsState()
    val connectionState by client.state.collectAsState()

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

    // Manage sink: add/remove video track from renderer
    LaunchedEffect(videoTrack) {
        val renderer = rendererRef.value
        val oldTrack = currentTrack.value
        val newTrack = videoTrack

        if (oldTrack != newTrack) {
            if (oldTrack != null && renderer != null) {
                try { oldTrack.removeSink(renderer) } catch (_: Exception) {}
            }
            if (newTrack != null && renderer != null) {
                newTrack.addSink(renderer)
                Log.i(TAG, "Video sink attached")
            }
            currentTrack.value = newTrack
        }
    }

    Box(modifier = modifier.background(Color.Black)) {
        AndroidView(
            factory = { ctx ->
                SurfaceViewRenderer(ctx).apply {
                    setZOrderMediaOverlay(true)
                    setEnableHardwareScaler(true)
                    setScalingType(RendererCommon.ScalingType.SCALE_ASPECT_FIT)
                    init(client.eglBase.eglBaseContext, null)
                    rendererRef.value = this

                    // Attach track if already available
                    videoTrack?.addSink(this)
                    currentTrack.value = videoTrack
                }
            },
            modifier = Modifier.matchParentSize(),
            onRelease = { renderer ->
                currentTrack.value?.removeSink(renderer)
                currentTrack.value = null
                rendererRef.value = null
                renderer.release()
            }
        )
    }
}
