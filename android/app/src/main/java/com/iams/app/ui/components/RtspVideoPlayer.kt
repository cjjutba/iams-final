package com.iams.app.ui.components

import android.view.TextureView
import androidx.annotation.OptIn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.rtsp.RtspMediaSource

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
        ExoPlayer.Builder(context).build().apply {
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
            override fun onPlayerError(error: PlaybackException) {
                onError?.invoke(error.message ?: "Playback error")
            }
        }
        player.addListener(listener)
        onDispose {
            player.removeListener(listener)
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
