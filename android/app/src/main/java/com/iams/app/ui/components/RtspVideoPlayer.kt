package com.iams.app.ui.components

import android.util.Log
import android.view.TextureView
import androidx.annotation.OptIn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.C
import androidx.media3.common.Format
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.VideoSize
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.analytics.AnalyticsListener
import androidx.media3.exoplayer.rtsp.RtspMediaSource

private const val TAG = "RtspPlayer"

@OptIn(UnstableApi::class)
@Composable
fun RtspVideoPlayer(
    rtspUrl: String,
    modifier: Modifier = Modifier,
    onTextureViewReady: ((TextureView) -> Unit)? = null,
    onError: ((String) -> Unit)? = null
) {
    val context = LocalContext.current

    val player = remember(rtspUrl) {
        Log.i(TAG, "Creating player for: $rtspUrl")

        val loadControl = DefaultLoadControl.Builder()
            .setBufferDurationsMs(
                /* minBufferMs = */ 100,
                /* maxBufferMs = */ 500,
                /* bufferForPlaybackMs = */ 0,
                /* bufferForPlaybackAfterRebufferMs = */ 100
            )
            .build()

        ExoPlayer.Builder(context)
            .setLoadControl(loadControl)
            .build().apply {
                // Skip audio decoding for lower latency on surveillance feeds
                trackSelectionParameters = trackSelectionParameters.buildUpon()
                    .setTrackTypeDisabled(C.TRACK_TYPE_AUDIO, true)
                    .build()

                val mediaSource = RtspMediaSource.Factory()
                    .setForceUseRtpTcp(true)
                    .createMediaSource(MediaItem.fromUri(rtspUrl))
                setMediaSource(mediaSource)
                playWhenReady = true
                prepare()
            }
    }

    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                val stateName = when (playbackState) {
                    Player.STATE_IDLE -> "IDLE"
                    Player.STATE_BUFFERING -> "BUFFERING"
                    Player.STATE_READY -> "READY"
                    Player.STATE_ENDED -> "ENDED"
                    else -> "UNKNOWN($playbackState)"
                }
                Log.i(TAG, "State: $stateName")

                if (playbackState == Player.STATE_READY && player.isCurrentMediaItemLive) {
                    player.seekToDefaultPosition()
                }
            }

            override fun onVideoSizeChanged(videoSize: VideoSize) {
                Log.i(TAG, "Video size: ${videoSize.width}x${videoSize.height}")
            }

            override fun onRenderedFirstFrame() {
                Log.i(TAG, "First frame rendered")
            }

            override fun onPlayerError(error: PlaybackException) {
                Log.e(TAG, "Player error: ${error.errorCodeName} - ${error.message}")
                onError?.invoke(error.message ?: "Playback error")
                player.prepare()
                player.play()
            }

            override fun onIsPlayingChanged(isPlaying: Boolean) {
                Log.i(TAG, "isPlaying: $isPlaying")
            }
        }

        // Analytics listener for frame drop/decode stats
        val analyticsListener = object : AnalyticsListener {
            private var lastLogTime = 0L

            override fun onDroppedVideoFrames(
                eventTime: AnalyticsListener.EventTime,
                droppedFrames: Int,
                elapsedMs: Long
            ) {
                Log.w(TAG, "Dropped $droppedFrames frames in ${elapsedMs}ms")
            }

            override fun onVideoDecoderInitialized(
                eventTime: AnalyticsListener.EventTime,
                decoderName: String,
                initializedTimestampMs: Long,
                initializationDurationMs: Long
            ) {
                Log.i(TAG, "Decoder: $decoderName (init ${initializationDurationMs}ms)")
            }

            override fun onDownstreamFormatChanged(
                eventTime: AnalyticsListener.EventTime,
                mediaLoadData: androidx.media3.exoplayer.source.MediaLoadData
            ) {
                val format = mediaLoadData.trackFormat
                if (format != null && format.sampleMimeType?.startsWith("video") == true) {
                    Log.i(TAG, "Video format: ${format.sampleMimeType} ${format.width}x${format.height} " +
                            "fps=${format.frameRate} bitrate=${format.bitrate}")
                }
            }
        }

        player.addListener(listener)
        player.addAnalyticsListener(analyticsListener)
        onDispose {
            player.removeListener(listener)
            player.removeAnalyticsListener(analyticsListener)
            player.release()
        }
    }

    AndroidView(
        factory = { ctx ->
            TextureView(ctx).also { textureView ->
                player.setVideoTextureView(textureView)
                onTextureViewReady?.invoke(textureView)
            }
        },
        modifier = modifier
    )
}
