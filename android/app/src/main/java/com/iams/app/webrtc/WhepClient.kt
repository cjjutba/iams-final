package com.iams.app.webrtc

import android.content.Context
import android.util.Log
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.webrtc.*
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Native WHEP (WebRTC-HTTP Egress Protocol) client for mediamtx.
 *
 * Replaces the WebView-based player with direct libwebrtc, providing
 * reliable video rendering via SurfaceViewRenderer.
 *
 * Signaling is a single HTTP POST: SDP offer → SDP answer (non-trickle ICE).
 */
class WhepClient(
    private val appContext: Context,
    private val whepUrl: String
) {
    companion object {
        private const val TAG = "WhepClient"
        private const val INITIAL_RECONNECT_DELAY = 1000L
        private const val MAX_RECONNECT_DELAY = 15000L
    }

    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()

    private val _videoTrack = MutableStateFlow<VideoTrack?>(null)
    val videoTrack = _videoTrack.asStateFlow()

    private val _state = MutableStateFlow<WhepConnectionState>(WhepConnectionState.Disconnected)
    val state = _state.asStateFlow()

    val eglBase: EglBase = EglBase.create()

    private var factory: PeerConnectionFactory? = null
    private var peerConnection: PeerConnection? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var reconnectJob: Job? = null
    private var reconnectDelay = INITIAL_RECONNECT_DELAY
    private var released = false

    private val iceServers = listOf(
        PeerConnection.IceServer.builder("stun:stun.l.google.com:19302")
            .createIceServer()
    )

    fun connect() {
        if (released) return
        reconnectJob?.cancel()
        _state.value = WhepConnectionState.Connecting

        scope.launch {
            try {
                ensureFactory()
                doConnect()
            } catch (e: Exception) {
                Log.e(TAG, "Connection failed: ${e.message}", e)
                _state.value = WhepConnectionState.Failed(e.message ?: "Unknown error")
                scheduleReconnect()
            }
        }
    }

    private fun ensureFactory() {
        if (factory != null) return

        PeerConnectionFactory.initialize(
            PeerConnectionFactory.InitializationOptions.builder(appContext)
                .setEnableInternalTracer(false)
                .createInitializationOptions()
        )

        factory = PeerConnectionFactory.builder()
            .setVideoDecoderFactory(DefaultVideoDecoderFactory(eglBase.eglBaseContext))
            .setVideoEncoderFactory(DefaultVideoEncoderFactory(eglBase.eglBaseContext, true, true))
            .createPeerConnectionFactory()
    }

    private suspend fun doConnect() {
        // Close any existing connection
        peerConnection?.dispose()
        peerConnection = null
        _videoTrack.value = null

        val iceGatheringComplete = CompletableDeferred<Unit>()

        val rtcConfig = PeerConnection.RTCConfiguration(iceServers).apply {
            sdpSemantics = PeerConnection.SdpSemantics.UNIFIED_PLAN
            continualGatheringPolicy = PeerConnection.ContinualGatheringPolicy.GATHER_ONCE
        }

        val pc = factory!!.createPeerConnection(rtcConfig, object : PeerConnection.Observer {
            override fun onIceGatheringChange(state: PeerConnection.IceGatheringState?) {
                Log.d(TAG, "ICE gathering: $state")
                if (state == PeerConnection.IceGatheringState.COMPLETE) {
                    iceGatheringComplete.complete(Unit)
                }
            }

            override fun onTrack(transceiver: RtpTransceiver?) {
                val track = transceiver?.receiver?.track()
                if (track is VideoTrack) {
                    Log.i(TAG, "Remote video track received")
                    _videoTrack.value = track
                }
            }

            override fun onConnectionChange(newState: PeerConnection.PeerConnectionState?) {
                Log.i(TAG, "Connection state: $newState")
                when (newState) {
                    PeerConnection.PeerConnectionState.CONNECTED -> {
                        _state.value = WhepConnectionState.Connected
                        reconnectDelay = INITIAL_RECONNECT_DELAY
                    }
                    PeerConnection.PeerConnectionState.FAILED -> {
                        _state.value = WhepConnectionState.Failed("ICE connection failed")
                        scheduleReconnect()
                    }
                    PeerConnection.PeerConnectionState.DISCONNECTED -> {
                        // Brief disconnection — may recover on its own
                        scope.launch {
                            delay(3000)
                            if (_state.value != WhepConnectionState.Connected) {
                                scheduleReconnect()
                            }
                        }
                    }
                    else -> {}
                }
            }

            override fun onSignalingChange(state: PeerConnection.SignalingState?) {}
            override fun onIceConnectionChange(state: PeerConnection.IceConnectionState?) {}
            override fun onIceConnectionReceivingChange(receiving: Boolean) {}
            override fun onIceCandidate(candidate: IceCandidate?) {}
            override fun onIceCandidatesRemoved(candidates: Array<out IceCandidate>?) {}
            override fun onAddStream(stream: MediaStream?) {}
            override fun onRemoveStream(stream: MediaStream?) {}
            override fun onDataChannel(dc: DataChannel?) {}
            override fun onRenegotiationNeeded() {}
        }) ?: throw IOException("Failed to create PeerConnection")

        peerConnection = pc

        // Add recv-only video transceiver
        pc.addTransceiver(
            MediaStreamTrack.MediaType.MEDIA_TYPE_VIDEO,
            RtpTransceiver.RtpTransceiverInit(RtpTransceiver.RtpTransceiverDirection.RECV_ONLY)
        )

        // Create and set local offer
        val offer = pc.awaitCreateOffer()
        pc.awaitSetLocalDescription(offer)

        // Wait for ICE gathering to complete (all candidates bundled in SDP)
        withTimeout(10_000) {
            iceGatheringComplete.await()
        }

        // POST offer to WHEP endpoint
        val localSdp = pc.localDescription?.description
            ?: throw IOException("Local description is null after ICE gathering")

        Log.i(TAG, "Sending WHEP offer to $whepUrl")
        val answer = postWhepOffer(localSdp)

        // Set remote answer
        val remoteDesc = SessionDescription(SessionDescription.Type.ANSWER, answer)
        pc.awaitSetRemoteDescription(remoteDesc)
        Log.i(TAG, "WHEP signaling complete, waiting for media...")
    }

    private fun postWhepOffer(sdpOffer: String): String {
        val body = sdpOffer.toRequestBody("application/sdp".toMediaType())
        val request = Request.Builder()
            .url(whepUrl)
            .post(body)
            .build()

        val response = httpClient.newCall(request).execute()
        if (!response.isSuccessful) {
            throw IOException("WHEP signaling failed: HTTP ${response.code}")
        }
        return response.body?.string() ?: throw IOException("Empty SDP answer")
    }

    private fun scheduleReconnect() {
        if (released) return
        reconnectJob?.cancel()
        _state.value = WhepConnectionState.Reconnecting
        reconnectJob = scope.launch {
            delay(reconnectDelay)
            reconnectDelay = (reconnectDelay * 2).coerceAtMost(MAX_RECONNECT_DELAY)
            Log.i(TAG, "Reconnecting to $whepUrl...")
            try {
                doConnect()
            } catch (e: Exception) {
                Log.e(TAG, "Reconnect failed: ${e.message}")
                _state.value = WhepConnectionState.Failed(e.message ?: "Reconnect failed")
                scheduleReconnect()
            }
        }
    }

    fun release() {
        released = true
        reconnectJob?.cancel()
        scope.cancel()
        _videoTrack.value = null
        peerConnection?.dispose()
        peerConnection = null
        factory?.dispose()
        factory = null
        eglBase.release()
    }
}

// --- SDP Observer coroutine helpers ---

private suspend fun PeerConnection.awaitCreateOffer(): SessionDescription =
    suspendCancellableCoroutine { cont ->
        createOffer(object : SdpObserver {
            override fun onCreateSuccess(sdp: SessionDescription) { cont.resumeWith(Result.success(sdp)) }
            override fun onCreateFailure(error: String) { cont.resumeWith(Result.failure(IOException("createOffer failed: $error"))) }
            override fun onSetSuccess() {}
            override fun onSetFailure(error: String) {}
        }, MediaConstraints())
    }

private suspend fun PeerConnection.awaitSetLocalDescription(sdp: SessionDescription) =
    suspendCancellableCoroutine { cont ->
        setLocalDescription(object : SdpObserver {
            override fun onSetSuccess() { cont.resumeWith(Result.success(Unit)) }
            override fun onSetFailure(error: String) { cont.resumeWith(Result.failure(IOException("setLocalDescription failed: $error"))) }
            override fun onCreateSuccess(sdp: SessionDescription) {}
            override fun onCreateFailure(error: String) {}
        }, sdp)
    }

private suspend fun PeerConnection.awaitSetRemoteDescription(sdp: SessionDescription) =
    suspendCancellableCoroutine { cont ->
        setRemoteDescription(object : SdpObserver {
            override fun onSetSuccess() { cont.resumeWith(Result.success(Unit)) }
            override fun onSetFailure(error: String) { cont.resumeWith(Result.failure(IOException("setRemoteDescription failed: $error"))) }
            override fun onCreateSuccess(sdp: SessionDescription) {}
            override fun onCreateFailure(error: String) {}
        }, sdp)
    }
