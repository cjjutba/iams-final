import { useEffect, useRef, useState, forwardRef, useImperativeHandle } from 'react'
import { AlertCircle, Loader2 } from 'lucide-react'

export interface WhepPlayerHandle {
  videoElement: HTMLVideoElement | null
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
}

type PlayerStatus = 'idle' | 'connecting' | 'playing' | 'error'

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
  { streamKey, fallbackStreamKey, baseUrl, className, onVideoSize, onActivePathChange },
  ref,
) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const pcRef = useRef<RTCPeerConnection | null>(null)
  const resourceUrlRef = useRef<string | null>(null)
  const [status, setStatus] = useState<PlayerStatus>('idle')
  const [errorMsg, setErrorMsg] = useState<string>('')

  useImperativeHandle(ref, () => ({
    get videoElement() {
      return videoRef.current
    },
  }))

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
      }

      pc.onconnectionstatechange = () => {
        if (cancelled) return
        const state = pc.connectionState
        if (state === 'connected') {
          setStatus('playing')
        } else if (state === 'failed' || state === 'disconnected' || state === 'closed') {
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
      />

      {status === 'connecting' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white">
          <Loader2 className="h-8 w-8 animate-spin" />
          <span className="text-sm">Connecting to {streamKey}…</span>
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
