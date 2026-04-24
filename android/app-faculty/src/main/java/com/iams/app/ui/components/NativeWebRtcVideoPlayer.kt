package com.iams.app.ui.components

import android.util.Log
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
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
 * Minimal WebRTC WHEP video viewer for the faculty app.
 *
 * 2026-04-22 two-app split simplification: the original player had ML Kit
 * frame-sink hooks for hybrid detection. The faculty app has no detection
 * overlays, so this variant is just:
 *   1. Create WhepClient, connect to the URL.
 *   2. Attach incoming VideoTrack to a SurfaceViewRenderer.
 *   3. Release resources on dispose.
 *
 * Attendance monitoring (boxes + names + presence) is handled in the admin
 * portal on the on-prem Mac.
 */
@Composable
fun NativeWebRtcVideoPlayer(
    whepUrl: String,
    modifier: Modifier = Modifier,
    onError: (String) -> Unit = {},
) {
    val context = LocalContext.current
    val client = remember(whepUrl) { WhepClient(context.applicationContext, whepUrl) }

    val videoTrack: VideoTrack? by client.videoTrack.collectAsState()
    val connectionState by client.state.collectAsState()

    LaunchedEffect(client) {
        client.connect()
    }

    LaunchedEffect(connectionState) {
        if (connectionState is WhepConnectionState.Failed) {
            val msg = (connectionState as WhepConnectionState.Failed).reason
            Log.w(TAG, "WHEP connection failed: $msg")
            onError(msg)
        }
    }

    DisposableEffect(client) {
        onDispose {
            client.release()
        }
    }

    Box(modifier = modifier.background(Color.Black)) {
        AndroidView(
            factory = { ctx ->
                SurfaceViewRenderer(ctx).apply {
                    // eglBase comes from the shared instance inside WhepClient.
                    init(client.eglBase.eglBaseContext, null)
                    setScalingType(RendererCommon.ScalingType.SCALE_ASPECT_FIT)
                    setEnableHardwareScaler(true)
                }
            },
            update = { renderer ->
                videoTrack?.addSink(renderer)
            },
            modifier = Modifier,
        )
    }
}
