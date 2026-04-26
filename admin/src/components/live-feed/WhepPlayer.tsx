import { useEffect, useRef, useState, forwardRef, useImperativeHandle } from 'react'
import { AlertCircle, Loader2 } from 'lucide-react'

/**
 * Per-decoded-frame metadata fanned out by ``onVideoFrame`` subscribers.
 * Sourced from ``HTMLVideoElement.requestVideoFrameCallback(metadata)``.
 *
 * - ``rtpTimestamp`` is the source RTP 90 kHz clock for H.264 WebRTC. It
 *   matches the backend's ``rtp_pts_90k`` from the WS frame_update because
 *   mediamtx forwards source RTP timestamps unchanged through WHEP egress
 *   (see deploy/mediamtx.onprem.yml comment dated 2026-04-25). Chromium
 *   exposes this; Safari does not — subscribers MUST handle ``undefined``
 *   by degrading gracefully (the frame-aligner falls back to the
 *   latest-only mode in that case).
 * - ``mediaTime`` is the video's own presentation time in seconds, on the
 *   ``<video>.currentTime`` clock. Useful as a fallback when ``rtpTimestamp``
 *   is unavailable.
 *
 * Live-feed plan 2026-04-25 Step 3.
 */
export interface VideoFrameMeta {
  rtpTimestamp: number | undefined
  mediaTime: number
  presentedFrames: number
}

export interface WhepPlayerHandle {
  videoElement: HTMLVideoElement | null
  /**
   * Subscribe to per-decoded-frame metadata. Returns an unsubscribe
   * function. Multiple subscribers are supported; the player only
   * registers ONE ``requestVideoFrameCallback`` loop and fans out.
   */
  onVideoFrame(cb: (meta: VideoFrameMeta) => void): () => void
}

interface WhepPlayerProps {
  /** Stream path on mediamtx — e.g. `eb226`. Corresponds to room.stream_key. */
  streamKey: string
  /**
   * Optional fallback path. If the primary `streamKey` returns 404 from
   * mediamtx (`{error: "no one is publishing to path ..."}`), the player
   * silently retries with this key. Used to degrade `eb226-sub` → `eb226`
   * when the sub stream isn't publishing so the admin still sees video.
   */
  fallbackStreamKey?: string
  /**
   * WHEP base URL. Defaults to VITE_STREAM_WEBRTC_URL (e.g. "/whep" in onprem).
   * Final URL: `{baseUrl}/{streamKey}/whep`.
   */
  baseUrl?: string
  className?: string
  /** Fires with the intrinsic video size once metadata loads. */
  onVideoSize?: (width: number, height: number) => void
  /** Fires once the player commits to a path — useful for the "showing main fallback" hint. */
  onActivePathChange?: (streamKey: string, isFallback: boolean) => void
  /**
   * Fires whenever the connection status changes. Lets the parent gate
   * overlays (bounding boxes, click targets) on `'playing'` so they don't
   * render on top of the "Connecting…" placeholder while frame data is
   * already streaming over the WebSocket.
   */
  onStatusChange?: (status: PlayerStatus) => void
}

export type PlayerStatus = 'idle' | 'connecting' | 'playing' | 'error'

/**
 * WebRTC WHEP client for the mediamtx live stream.
 *
 * Key details per project lessons:
 * - mediamtx is NON-trickle ICE — we must wait for ICE gathering to COMPLETE
 *   before POSTing the offer, or the SDP will be missing candidates and the
 *   connection fails silently (lessons 2026-03-21).
 * - Use unified-plan + audio-only addTransceiver won't help; we're recv-only
 *   for video.
 * - We DELETE the resource on unmount to free mediamtx's reader slot.
 */
export const WhepPlayer = forwardRef<WhepPlayerHandle, WhepPlayerProps>(function WhepPlayer(
  { streamKey, fallbackStreamKey, baseUrl, className, onVideoSize, onActivePathChange, onStatusChange },
  ref,
) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const pcRef = useRef<RTCPeerConnection | null>(null)
  const resourceUrlRef = useRef<string | null>(null)
  const [status, setStatus] = useState<PlayerStatus>('idle')
  const [errorMsg, setErrorMsg] = useState<string>('')

  // Notify parent on status transitions so overlays can be gated on
  // 'playing' instead of just "WS data has arrived".
  useEffect(() => {
    onStatusChange?.(status)
  }, [status, onStatusChange])

  // Per-decoded-frame subscribers (live-feed plan 2026-04-25 Step 3c).
  // The set is mutated by ``onVideoFrame`` (returned via the imperative
  // handle); the rVFC loop iterates it on every callback. We register one
  // and only one loop on the <video> element regardless of subscriber
  // count.
  const frameSubscribersRef = useRef<Set<(meta: VideoFrameMeta) => void>>(new Set())

  useImperativeHandle(ref, () => ({
    get videoElement() {
      return videoRef.current
    },
    onVideoFrame(cb) {
      frameSubscribersRef.current.add(cb)
      return () => {
        frameSubscribersRef.current.delete(cb)
      }
    },
  }))

  // requestVideoFrameCallback fanout. The browser fires ``frameCb`` once
  // per *decoded* video frame with metadata (rtpTimestamp, mediaTime,
  // etc.). We loop by re-registering inside the callback. On Safari the
  // method is absent — we no-op so subscribers receive nothing and the
  // frame-aligner falls back to its latest-only mode.
  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    // Type guard: Chromium exposes the method; tests mock it on; Safari
    // omits it entirely. We feature-detect rather than rely on @types.
    const rvfc = (video as HTMLVideoElement & {
      requestVideoFrameCallback?: (cb: (now: number, metadata: {
        rtpTimestamp?: number
        mediaTime: number
        presentedFrames: number
      }) => void) => number
      cancelVideoFrameCallback?: (handle: number) => void
    })
    if (typeof rvfc.requestVideoFrameCallback !== 'function') return

    let handle: number | null = null
    let cancelled = false

    const tick = (_now: number, metadata: { rtpTimestamp?: number; mediaTime: number; presentedFrames: number }) => {
      if (cancelled) return
      const subs = frameSubscribersRef.current
      if (subs.size > 0) {
        const meta: VideoFrameMeta = {
          rtpTimestamp: metadata.rtpTimestamp,
          mediaTime: metadata.mediaTime,
          presentedFrames: metadata.presentedFrames,
        }
        // Run subscribers under try/catch so one bad consumer can't kill
        // the loop for the rest.
        for (const cb of subs) {
          try {
            cb(meta)
          } catch (err) {
            console.warn('[WhepPlayer] onVideoFrame subscriber threw', err)
          }
        }
      }
      handle = rvfc.requestVideoFrameCallback!(tick)
    }
    handle = rvfc.requestVideoFrameCallback(tick)

    return () => {
      cancelled = true
      if (handle != null && typeof rvfc.cancelVideoFrameCallback === 'function') {
        try {
          rvfc.cancelVideoFrameCallback(handle)
        } catch {
          /* ignore */
        }
      }
    }
  }, [])

  useEffect(() => {
    if (!streamKey) return
    const base = (baseUrl ?? String(import.meta.env.VITE_STREAM_WEBRTC_URL ?? '/whep')).replace(/\/$/, '')

    let cancelled = false

    // Try `key`, returning true on success, false on a 404 (so the caller can
    // try a fallback), and throwing on any other error.
    const attempt = async (key: string): Promise<boolean> => {
      const whepUrl = `${base}/${key}/whep`

      // Tear down any previous PeerConnection from a prior attempt.
      const prev = pcRef.current
      pcRef.current = null
      if (prev) prev.close()

      const pc = new RTCPeerConnection({
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
      })
      pcRef.current = pc

      pc.addTransceiver('video', { direction: 'recvonly' })
      pc.addTransceiver('audio', { direction: 'recvonly' })

      pc.ontrack = (event) => {
        if (cancelled) return
        if (videoRef.current && event.streams[0]) {
          videoRef.current.srcObject = event.streams[0]
        }

        // Latency-critical: cap the WebRTC jitter buffer.
        //
        // Chromium's default playout delay targets ~200 ms to absorb network
        // jitter — appropriate for cross-internet conferencing, way more than
        // we need on IAMS-Net. Setting playoutDelayHint=0 asks the receiver to
        // minimise buffering (Chrome won't actually go to 0; it lands around
        // 30-50 ms in practice). On a LAN that's the difference between video
        // that "feels live" and video that always looks ~200 ms behind.
        //
        // contentHint='motion' tells the decoder to prefer smoothness over
        // still-image quality — sensible for a CCTV feed where motion is the
        // whole point.
        //
        // Both APIs are Chromium-only. Safari ignores them silently. Brave is
        // Chromium-based so they apply here. Wrap in try/catch for safety:
        // older Chromium versions reject playoutDelayHint=0 with a TypeError
        // (Chrome <94, very rare in 2026 but cheap insurance).
        try {
          for (const receiver of pc.getReceivers()) {
            if (receiver.track?.kind === 'video') {
              const r = receiver as RTCRtpReceiver & { playoutDelayHint?: number }
              if ('playoutDelayHint' in receiver) {
                r.playoutDelayHint = 0
              }
              try {
                receiver.track.contentHint = 'motion'
              } catch {
                /* Safari etc. */
              }
            }
          }
        } catch (err) {
          console.debug('[WhepPlayer] playoutDelayHint not supported', err)
        }
      }

      pc.onconnectionstatechange = () => {
        if (cancelled) return
        const state = pc.connectionState
        // Don't flip to 'playing' here. WebRTC `connected` only means the
        // SRTP transport is up — it can fire several hundred ms before the
        // first I-frame is decoded and presented. If we promote status to
        // 'playing' on the transport event, the parent un-gates the bbox
        // overlay and DetectionOverlay paints labels on top of an
        // all-black <video>. Wait for the <video>'s `onPlaying` event
        // (fired below) so the overlay and the first decoded frame appear
        // simultaneously.
        if (state === 'failed' || state === 'disconnected' || state === 'closed') {
          setStatus('error')
          setErrorMsg(`WebRTC ${state}`)
        }
      }

      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)

      // WAIT for ICE gathering to finish. mediamtx requires all candidates
      // in the SDP (non-trickle). See lessons 2026-03-21.
      await new Promise<void>((resolve) => {
        if (pc.iceGatheringState === 'complete') {
          resolve()
          return
        }
        const checkState = () => {
          if (pc.iceGatheringState === 'complete') {
            pc.removeEventListener('icegatheringstatechange', checkState)
            resolve()
          }
        }
        pc.addEventListener('icegatheringstatechange', checkState)
        setTimeout(() => {
          pc.removeEventListener('icegatheringstatechange', checkState)
          resolve()
        }, 3000)
      })

      if (cancelled) {
        pc.close()
        return false
      }

      const localSdp = pc.localDescription?.sdp
      if (!localSdp) throw new Error('Failed to generate local SDP')

      const response = await fetch(whepUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/sdp' },
        body: localSdp,
      })

      if (response.status === 404) {
        // "no one is publishing to path …" — caller may want to try fallback.
        pc.close()
        if (pcRef.current === pc) pcRef.current = null
        return false
      }

      if (!response.ok) {
        throw new Error(`WHEP server returned ${response.status}: ${await response.text()}`)
      }

      const location = response.headers.get('Location')
      if (location) {
        resourceUrlRef.current = new URL(location, window.location.origin + whepUrl).toString()
      }

      const answerSdp = await response.text()
      if (cancelled) {
        pc.close()
        return false
      }

      await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp })
      return true
    }

    const connect = async () => {
      setStatus('connecting')
      setErrorMsg('')

      try {
        const primaryOk = await attempt(streamKey)
        if (primaryOk) {
          onActivePathChange?.(streamKey, false)
          return
        }

        if (cancelled) return

        if (fallbackStreamKey && fallbackStreamKey !== streamKey) {
          console.warn(
            `[WhepPlayer] "${streamKey}" is not publishing; falling back to "${fallbackStreamKey}"`,
          )
          const fallbackOk = await attempt(fallbackStreamKey)
          if (fallbackOk) {
            onActivePathChange?.(fallbackStreamKey, true)
            return
          }
          if (cancelled) return
          setStatus('error')
          setErrorMsg(
            `Neither "${streamKey}" nor "${fallbackStreamKey}" is currently publishing to mediamtx.`,
          )
          return
        }

        setStatus('error')
        setErrorMsg(`"${streamKey}" is not publishing to mediamtx.`)
      } catch (err) {
        if (cancelled) return
        console.error('[WhepPlayer] connection failed', err)
        setStatus('error')
        setErrorMsg(err instanceof Error ? err.message : 'Unknown error')
        const pc = pcRef.current
        if (pc) {
          pc.close()
          pcRef.current = null
        }
      }
    }

    connect()

    return () => {
      cancelled = true
      const pc = pcRef.current
      pcRef.current = null

      if (pc) {
        pc.close()
      }

      const resourceUrl = resourceUrlRef.current
      resourceUrlRef.current = null
      if (resourceUrl) {
        fetch(resourceUrl, { method: 'DELETE' }).catch(() => {})
      }

      if (videoRef.current) {
        videoRef.current.srcObject = null
      }
    }
  }, [streamKey, fallbackStreamKey, baseUrl, onActivePathChange])

  return (
    <div className={`relative bg-black ${className ?? ''}`}>
      <video
        ref={videoRef}
        className="h-full w-full object-contain"
        autoPlay
        playsInline
        muted
        onLoadedMetadata={(e) => {
          const v = e.currentTarget
          if (v.videoWidth && v.videoHeight) {
            onVideoSize?.(v.videoWidth, v.videoHeight)
          }
        }}
        onPlaying={() => {
          // Only escalate if we're still in the connecting phase. We must
          // not clobber 'error' (real disconnection observed by
          // onconnectionstatechange after playback started) or 'idle'
          // (effect torn down).
          setStatus((prev) => (prev === 'connecting' ? 'playing' : prev))
        }}
        onWaiting={() => {
          // Live stream stalled out (publisher dropped frames, or sub
          // ffmpeg restarted). Demote to 'connecting' so the parent
          // re-hides the overlay until decoded frames resume — otherwise
          // we'd paint boxes on the last freeze-frame.
          setStatus((prev) => (prev === 'playing' ? 'connecting' : prev))
        }}
      />

      {status === 'connecting' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white">
          <Loader2 className="h-8 w-8 animate-spin" />
          <span className="text-sm">
            Connecting to {streamKey.replace(/-sub$/, '').toUpperCase()} camera…
          </span>
        </div>
      )}

      {status === 'error' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white">
          <AlertCircle className="h-8 w-8 text-destructive" />
          <span className="text-sm font-medium">Stream unavailable</span>
          <span className="text-xs text-white/70 max-w-md text-center px-4">{errorMsg}</span>
        </div>
      )}
    </div>
  )
})
