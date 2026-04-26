import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2, Play, Square, Timer, Video } from 'lucide-react'
import { toast } from 'sonner'

import { WhepPlayer, type WhepPlayerHandle, type PlayerStatus } from '@/components/live-feed/WhepPlayer'
import { DetectionOverlay } from '@/components/live-feed/DetectionOverlay'
import { AttendancePanel } from '@/components/live-feed/AttendancePanel'
import { RecognitionPanel } from '@/components/live-feed/RecognitionPanel'
import { OverlayClickTargets } from '@/components/live-feed/OverlayClickTargets'
import { TrackDetailSheet } from '@/components/live-feed/TrackDetailSheet'
import { TrackDetailMiniPanel } from '@/components/live-feed/TrackDetailMiniPanel'
import { SessionStatusPill } from '@/components/live-feed/SessionStatusPill'
import { VideoHud } from '@/components/live-feed/VideoHud'
import { VideoFullscreenButton } from '@/components/live-feed/VideoFullscreenButton'
import { useAttendanceWs } from '@/hooks/use-attendance-ws'
import { useFrameAligner } from '@/hooks/use-frame-aligner'
import { useSchedule, useRoom, useSessionStartEligibility } from '@/hooks/use-queries'
import type { SessionEligibility, SessionEligibilityCode } from '@/services/presence.service'
import { usePageTitle } from '@/hooks/use-page-title'
import { useBreadcrumbStore } from '@/stores/breadcrumb.store'
import { useTrackSelectionStore } from '@/stores/track-selection.store'
import api from '@/services/api'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Skeleton } from '@/components/ui/skeleton'
import { EarlyLeaveTimeoutControl } from '@/components/schedules/early-leave-timeout-control'

/**
 * Derive the mediamtx stream key from a room's camera_endpoint.
 * Example: "rtsp://mediamtx:8554/eb226" → "eb226".
 * Falls back to the room name lowercased if the endpoint doesn't parse.
 */
function deriveStreamKey(cameraEndpoint: string | null | undefined, roomName: string): string {
  if (cameraEndpoint) {
    const match = cameraEndpoint.match(/\/([^/]+)(?:\?.*)?$/)
    if (match?.[1]) return match[1].toLowerCase()
  }
  return roomName.toLowerCase().replace(/\s+/g, '')
}

function formatClock(date: Date): string {
  return date
    .toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true })
    .replace(/^0/, '')
}

/**
 * Re-evaluate the server's eligibility snapshot against the current wall
 * clock. The backend snapshot is the source of truth for ALREADY_RAN_TODAY
 * and ownership/active-status, but for time-window codes (TOO_EARLY,
 * AFTER_END) the snapshot becomes stale between polls. This recomputes
 * those two from `scheduled_start` / `scheduled_end` / `available_at` so
 * the button flips at the actual minute boundary without a refetch.
 *
 * Returns the eligibility unchanged if it's not a window-related code, or
 * if the original snapshot is missing.
 */
function refreshTimeWindow(
  eligibility: SessionEligibility | undefined,
  now: Date,
): SessionEligibility | undefined {
  if (!eligibility) return eligibility

  // Only TOO_EARLY / AFTER_END / ALLOWED can flip from a clock tick. The
  // others are sticky for the rest of the day from the server's POV.
  const windowCodes: SessionEligibilityCode[] = ['ALLOWED', 'TOO_EARLY', 'AFTER_END']
  if (!windowCodes.includes(eligibility.code)) return eligibility

  const start = new Date(eligibility.scheduled_start)
  const end = new Date(eligibility.scheduled_end)
  const availableAt = new Date(eligibility.available_at)

  if (now < availableAt) {
    return {
      ...eligibility,
      allowed: false,
      code: 'TOO_EARLY',
      message: `Manual start opens at ${formatClock(availableAt)} (10 minutes before scheduled start).`,
    }
  }
  if (now >= end) {
    return {
      ...eligibility,
      allowed: false,
      code: 'AFTER_END',
      message: `This schedule ended at ${formatClock(end)} today.`,
    }
  }
  // Inside the window — let the server's verdict stand (it may still be
  // RUNNING / ALREADY_RAN_TODAY, which a clock tick cannot resolve).
  if (eligibility.code === 'ALLOWED') return eligibility
  // Was TOO_EARLY/AFTER_END from server but clock has rolled into window
  // — preemptively flip to allowed; the next server poll will confirm.
  return {
    ...eligibility,
    allowed: true,
    code: 'ALLOWED',
    message: `Ready to start (within scheduled window ${formatClock(start)}–${formatClock(end)}).`,
  }
}

export default function ScheduleLivePage() {
  const { id: scheduleId } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: schedule, isLoading: schedLoading } = useSchedule(scheduleId ?? '')
  const { data: room, isLoading: roomLoading } = useRoom(schedule?.room_id ?? '')

  const streamKey = useMemo(() => {
    if (!schedule || !room) return null
    return deriveStreamKey(room.camera_endpoint, room.name)
  }, [schedule, room])

  // The admin display pulls the camera SUB stream (e.g. `eb226-sub`), not
  // the MAIN stream that the ML pipeline decodes. Reasons:
  //   1. The browser viewport is ~1280-wide — 2304×1296 is wasted bytes
  //      and decode cycles even on Apple-Silicon hardware decoders.
  //   2. CRITICAL: the api-gateway's FrameGrabber is always-on for every
  //      camera-equipped room (per the 2026-04-25 always-on-grabbers
  //      change in app/main.py). It holds a permanent RTSP reader on the
  //      main path from boot. If the browser also reads main via WHEP,
  //      mediamtx must fan the same publisher out to two readers
  //      simultaneously — empirically this causes WebRTC jitter-buffer
  //      drift and intermittent black screens during ICE renegotiation
  //      when the two readers' keyframe waits collide.
  //   3. Sub gives the browser its own independent path (the cam-relay
  //      supervisor publishes both profiles), so admin display and ML
  //      pipeline don't compete.
  // Sub paths are provisioned by scripts/iams-cam-relay.sh + the
  // `~^.+-sub$` path in deploy/mediamtx.onprem.yml.
  //
  // We tried main-as-default on 2026-04-25, then RETESTED 2026-04-25
  // evening after the ML-sidecar split (hoping the sidecar's offload of
  // CPU SCRFD would relieve the contention). It did NOT — "Stream
  // unavailable / WebRTC disconnected" reproduced cleanly on EB226 under
  // the same dual-reader pattern, and the player auto-fell-back to sub.
  // Confirms the failure mode is at the mediamtx publisher→reader fanout
  // layer, not the api-gateway compute side. Don't re-enable without
  // first solving the contention (separate ffmpeg fanout to a `-display`
  // path so each consumer has its own publisher; HLS for admin instead
  // of WHEP; or backend display-delay buffering on the WS overlay path
  // so sub-stream sync is achieved by adding latency, not by changing
  // source).
  const displayStreamKey = useMemo(() => {
    return streamKey ? `${streamKey}-sub` : null
  }, [streamKey])

  // Main stream becomes the auto-fallback if sub isn't publishing
  // (e.g. cam-relay supervisor restarted the sub ffmpeg). Better to
  // show heavyweight video than a black box.
  const fallbackStreamKey = useMemo(() => {
    return streamKey ?? null
  }, [streamKey])

  usePageTitle(
    schedule?.subject_code ? `Live · ${schedule.subject_code}` : 'Live Feed',
  )

  const setBreadcrumbLabel = useBreadcrumbStore((s) => s.setLabel)
  useEffect(() => {
    setBreadcrumbLabel(
      schedule?.subject_code ? `${schedule.subject_code} — Live` : 'Live Feed',
    )
    return () => setBreadcrumbLabel(null)
  }, [setBreadcrumbLabel, schedule?.subject_code])

  const {
    isConnected,
    latestFrame,
    latestSummary,
    latestSessionEvent,
    recognitionEvents,
    liveCrops,
    latencyStats,
    downloadLatencyCsv,
    clearLatencySamples,
  } = useAttendanceWs(scheduleId)

  const playerRef = useRef<WhepPlayerHandle>(null)
  const videoContainerRef = useRef<HTMLDivElement>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  useEffect(() => {
    const sync = () => setIsFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', sync)
    return () => document.removeEventListener('fullscreenchange', sync)
  }, [])
  const [videoSize, setVideoSize] = useState<{ width: number; height: number } | null>(null)
  const [activeStream, setActiveStream] = useState<{ key: string; isFallback: boolean } | null>(null)
  const [playerStatus, setPlayerStatus] = useState<PlayerStatus>('idle')
  const handleActivePathChange = useCallback((key: string, isFallback: boolean) => {
    setActiveStream({ key, isFallback })
  }, [])
  const handleStatusChange = useCallback((status: PlayerStatus) => {
    setPlayerStatus(status)
  }, [])

  // Hide bbox overlays + click targets until the WebRTC stream is actually
  // playing. WS frame_update events can arrive before the video element
  // has its first decoded frame (during SDP/ICE negotiation), which used
  // to draw stale boxes on top of the "Connecting to <key>…" placeholder
  // — misleading UX where labels appear without a video to anchor them.
  const overlaysVisible = playerStatus === 'playing'

  // RTP-PTS-based frame aligner (live-feed plan 2026-04-25 Step 3c).
  // Behind ``VITE_ENABLE_FRAME_ALIGN`` so we can A/B against the
  // post-Step-1 honest-blink behavior. The hook returns the bbox set
  // that semantically matches whichever video frame the WHEP player
  // just decoded; passes through ``latestFrame.tracks`` when disabled
  // or unsupported (Safari, legacy backend).
  const frameAlignEnabled = String(import.meta.env.VITE_ENABLE_FRAME_ALIGN ?? '') === '1'
  const alignedTracks = useFrameAligner(playerRef.current, latestFrame, {
    enabled: frameAlignEnabled,
  })

  const selectedTrackId = useTrackSelectionStore((s) => s.selectedTrackId)
  const selectTrack = useTrackSelectionStore((s) => s.select)
  const clearTrackSelection = useTrackSelectionStore((s) => s.clear)
  // Clear selection on schedule change so the sheet doesn't leak across pages.
  useEffect(() => {
    clearTrackSelection()
  }, [scheduleId, clearTrackSelection])

  const [sessionLoading, setSessionLoading] = useState(false)
  const [sessionActive, setSessionActive] = useState<boolean | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)

  // Server-side eligibility snapshot (refetched every 30s; manual refetch
  // after a failed Start to pick up ALREADY_RAN_TODAY transitions).
  const {
    data: eligibilitySnapshot,
    refetch: refetchEligibility,
  } = useSessionStartEligibility(scheduleId)

  // Tick once per second so TOO_EARLY → ALLOWED → AFTER_END transitions
  // happen at the minute boundary instead of waiting on the next server
  // poll. Cheap — just a Date assignment and a boolean flip.
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1_000)
    return () => clearInterval(t)
  }, [])

  // Effective eligibility = server snapshot reconciled against wall clock.
  // The "running" verdict from sessionActive (REST/WS) takes precedence
  // over the server snapshot's RUNNING code, since it updates instantly
  // on session_start / session_end events.
  const eligibility = useMemo<SessionEligibility | undefined>(() => {
    if (sessionActive === true && eligibilitySnapshot) {
      return { ...eligibilitySnapshot, allowed: false, code: 'RUNNING', message: 'Session is already running.' }
    }
    return refreshTimeWindow(eligibilitySnapshot, now)
  }, [eligibilitySnapshot, sessionActive, now])

  const startButtonDisabled =
    sessionLoading || (!!eligibility && !eligibility.allowed)
  const startButtonTitle =
    eligibility && !eligibility.allowed && eligibility.code !== 'RUNNING'
      ? eligibility.message
      : undefined

  // Poll session active state on mount + every 10 s.
  // The 10 s cadence is intentionally tighter than the backend's 15 s
  // session_lifecycle_check so that an auto-start/auto-end triggered by
  // the schedule time window becomes visible to the admin within one
  // lifecycle cycle plus one UI poll (~≤25 s worst case).
  useEffect(() => {
    if (!scheduleId) return
    let active = true

    const check = async () => {
      try {
        // Backend returns `active_sessions` as a flat list of schedule UUIDs,
        // not an array of objects. The earlier `.some(s => s.schedule_id)`
        // shape was wrong and always resolved to false, which made the
        // "Session not running" card stick even after Start Session succeeded
        // (documented 2026-04-22).
        const res = await api.get<{ active_sessions: string[]; count?: number }>(
          '/presence/sessions/active',
        )
        if (!active) return
        const running = res.data.active_sessions?.includes(scheduleId!) ?? false
        setSessionActive(running)
      } catch {
        if (active) setSessionActive(null)
      }
    }

    check()
    const interval = setInterval(check, 10_000)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [scheduleId])

  // WebSocket session_start / session_end lets the button flip instantly
  // when the lifecycle job (or another admin) starts/ends the session,
  // without waiting for the next REST poll.
  useEffect(() => {
    if (!latestSessionEvent) return
    if (latestSessionEvent.schedule_id !== scheduleId) return
    if (latestSessionEvent.event === 'session_start') {
      setSessionActive(true)
    } else if (latestSessionEvent.event === 'session_end') {
      setSessionActive(false)
    }
  }, [latestSessionEvent, scheduleId])

  const startSession = async () => {
    if (!scheduleId) return
    setSessionLoading(true)
    try {
      await api.post('/presence/sessions/start', { schedule_id: scheduleId })
      setSessionActive(true)
      toast.success('Session started')
    } catch (err: unknown) {
      // The backend returns a structured detail object for window/owner
      // gating rejections (`{code, message, ...}`) and a plain string for
      // older errors. Handle both shapes.
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      let msg: string
      if (detail && typeof detail === 'object' && 'message' in detail) {
        msg = String((detail as { message: unknown }).message)
      } else if (typeof detail === 'string') {
        msg = detail
      } else if (err instanceof Error) {
        msg = err.message
      } else {
        msg = 'Failed to start session'
      }
      toast.error(msg)
      // Re-poll eligibility so the button reflects the rejection reason
      // (especially ALREADY_RAN_TODAY, which we can't predict locally).
      void refetchEligibility()
    } finally {
      setSessionLoading(false)
    }
  }

  const endSession = async () => {
    if (!scheduleId) return
    setSessionLoading(true)
    try {
      // Backend's /sessions/end expects schedule_id as a query param (matches
      // the Android apps). Sending it in the body would 422 — which is what
      // the admin portal was doing before this fix, silently breaking End
      // Session until the next lifecycle tick auto-ended the session.
      await api.post('/presence/sessions/end', null, {
        params: { schedule_id: scheduleId },
      })
      setSessionActive(false)
      toast.success('Session ended')
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (err instanceof Error ? err.message : 'Failed to end session')
      toast.error(msg)
    } finally {
      setSessionLoading(false)
    }
  }

  if (schedLoading || roomLoading) {
    // Mirror the loaded layout (header → video card → attendance + recognition
    // panels) so the cut-over to real data doesn't shift the page. Each
    // skeleton block is sized to match its eventual counterpart.
    return (
      <div className="flex flex-col gap-4 p-4 md:p-6">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-2">
            <Skeleton className="-ml-2 mt-0.5 h-8 w-8 shrink-0 rounded-md" />
            <div className="min-w-0 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <Skeleton className="h-6 w-72" />
                <Skeleton className="h-5 w-16 rounded-full" />
              </div>
              <Skeleton className="h-4 w-48" />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Skeleton className="h-9 w-9 rounded-md" />
            <Skeleton className="h-9 w-32 rounded-md" />
          </div>
        </div>

        {/* Video + Right rail */}
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          {/* Video card skeleton — match aspect-video ratio + corner HUD chip */}
          <Card className="overflow-hidden">
            <CardContent className="p-0">
              <div className="relative aspect-video w-full overflow-hidden bg-gradient-to-br from-zinc-900 via-zinc-950 to-black">
                <div
                  className="absolute left-[14%] top-[28%] h-[34%] w-[14%] rounded-md border border-white/10 bg-white/[0.04] animate-pulse"
                  aria-hidden
                />
                <div
                  className="absolute left-[42%] top-[34%] h-[30%] w-[12%] rounded-md border border-white/10 bg-white/[0.04] animate-pulse"
                  style={{ animationDelay: '180ms' }}
                  aria-hidden
                />
                <div
                  className="absolute right-[18%] top-[30%] h-[32%] w-[13%] rounded-md border border-white/10 bg-white/[0.04] animate-pulse"
                  style={{ animationDelay: '360ms' }}
                  aria-hidden
                />
                <div className="absolute right-3 top-3 h-7 w-36 rounded-md border border-white/10 bg-white/[0.06] animate-pulse" />
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
                  <Loader2 className="h-7 w-7 animate-spin text-white/60" />
                  <span className="text-xs text-white/55">Loading schedule…</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Right rail skeleton — attendance card + recognition panel */}
          <div className="flex flex-col gap-4 lg:min-h-[500px]">
            <Card className="flex flex-col">
              <div className="space-y-3 p-4 pb-3">
                <div className="flex items-center justify-between">
                  <Skeleton className="h-5 w-24" />
                  <Skeleton className="h-2 w-2 rounded-full" />
                </div>
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-1.5 w-full rounded-full" />
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-3 w-16" />
                  ))}
                </div>
              </div>
              <div className="space-y-4 px-4 py-3">
                {Array.from({ length: 3 }).map((_, group) => (
                  <div key={group} className="space-y-2">
                    <Skeleton className="h-3 w-20" />
                    {Array.from({ length: 2 }).map((_, row) => (
                      <div key={row} className="flex items-center gap-3 px-2 py-2">
                        <div className="min-w-0 flex-1 space-y-1.5">
                          <Skeleton className="h-3.5 w-32" />
                          <Skeleton className="h-2.5 w-20" />
                        </div>
                        <Skeleton className="h-5 w-16 shrink-0 rounded-full" />
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </Card>

            <Card className="flex h-[420px] flex-col">
              <div className="space-y-2 p-4 pb-3">
                <div className="flex items-center justify-between">
                  <Skeleton className="h-5 w-36" />
                  <Skeleton className="h-3 w-12" />
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Skeleton className="h-7 w-20 rounded-md" />
                  <Skeleton className="h-7 w-28 rounded-md" />
                  <Skeleton className="ml-auto h-3 w-32" />
                </div>
              </div>
              <div className="flex-1 space-y-2 overflow-hidden px-4 py-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="flex gap-3 py-2">
                    <Skeleton className="h-12 w-12 shrink-0 rounded-md" />
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <Skeleton className="h-3 w-24" />
                        <Skeleton className="h-4 w-12 rounded-full" />
                      </div>
                      <Skeleton className="h-1.5 w-full rounded-full" />
                      <div className="flex items-center justify-between">
                        <Skeleton className="h-2.5 w-20" />
                        <Skeleton className="h-2.5 w-24" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      </div>
    )
  }

  if (!schedule || !room || !streamKey) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12 text-center">
        <Video className="h-12 w-12 text-muted-foreground" />
        <h2 className="text-lg font-semibold">Schedule or room unavailable</h2>
        <p className="text-sm text-muted-foreground max-w-md">
          The live feed needs a schedule with an assigned room that has a camera
          endpoint configured. Check the schedule's room in the Rooms section.
        </p>
        <Button variant="outline" onClick={() => navigate('/schedules')}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Schedules
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate(`/schedules/${scheduleId}`)}
            aria-label="Back to schedule"
            title="Back to schedule"
            className="-ml-2 mt-0.5 h-8 w-8 shrink-0"
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold leading-tight">
                {schedule.subject_code}{' '}
                <span className="text-muted-foreground">·</span>{' '}
                <span className="font-normal">{schedule.subject_name}</span>
              </h1>
              <SessionStatusPill sessionActive={sessionActive} eligibility={eligibility} />
            </div>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {room.name}
              {room.building ? ` · ${room.building}` : ''}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Popover open={settingsOpen} onOpenChange={setSettingsOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                size="icon"
                title="Attendance settings"
                aria-label="Attendance settings"
                className="h-9 w-9"
              >
                <Timer className="h-4 w-4" />
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-80">
              <div className="mb-3 flex items-start gap-2">
                <Timer className="mt-0.5 h-4 w-4 text-muted-foreground" />
                <div className="space-y-0.5">
                  <div className="text-sm font-medium">Early-leave threshold</div>
                  <p className="text-xs text-muted-foreground">
                    {sessionActive === true
                      ? 'Saving applies live to this running session.'
                      : 'Saved value will be used the next time this schedule runs.'}
                  </p>
                </div>
              </div>
              <EarlyLeaveTimeoutControl
                scheduleId={schedule.id}
                currentMinutes={schedule.early_leave_timeout_minutes ?? null}
                inline
                onSaved={() => setSettingsOpen(false)}
              />
            </PopoverContent>
          </Popover>
          {sessionActive === true ? (
            <Button
              variant="outline"
              onClick={endSession}
              disabled={sessionLoading}
              className="gap-2"
            >
              {sessionLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Square className="h-4 w-4" />
              )}
              End Session
            </Button>
          ) : (
            <Button
              onClick={startSession}
              disabled={startButtonDisabled}
              title={startButtonTitle}
              className="gap-2"
            >
              {sessionLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Start Session
            </Button>
          )}
        </div>
      </div>

      {/* Video + Overlay | Attendance Panel */}
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            <div
              ref={videoContainerRef}
              className={`group relative w-full bg-black ${isFullscreen ? 'h-screen' : 'aspect-video'}`}
            >
              <WhepPlayer
                ref={playerRef}
                streamKey={displayStreamKey ?? streamKey}
                fallbackStreamKey={fallbackStreamKey ?? undefined}
                className="h-full w-full"
                onVideoSize={(w, h) => setVideoSize({ width: w, height: h })}
                onActivePathChange={handleActivePathChange}
                onStatusChange={handleStatusChange}
              />
              {overlaysVisible && (
                <>
                  <OverlayClickTargets
                    tracks={latestFrame?.tracks ?? []}
                    videoElement={playerRef.current?.videoElement ?? null}
                    videoSize={videoSize}
                  />
                  <DetectionOverlay
                    tracks={frameAlignEnabled ? alignedTracks : (latestFrame?.tracks ?? [])}
                    videoElement={playerRef.current?.videoElement ?? null}
                    videoSize={videoSize}
                    selectedTrackId={selectedTrackId}
                  />
                </>
              )}
              <VideoHud
                latestFrame={latestFrame}
                latencyStats={latencyStats}
                onDownloadCsv={downloadLatencyCsv}
                onClearSamples={clearLatencySamples}
                fallbackActive={activeStream?.isFallback ?? false}
                fallbackKey={activeStream?.key}
                portalContainer={isFullscreen ? videoContainerRef.current : null}
              />
              <VideoFullscreenButton targetRef={videoContainerRef} />
              {isFullscreen && (
                <TrackDetailMiniPanel
                  latestFrame={latestFrame}
                  latestSummary={latestSummary}
                  isConnected={isConnected}
                  scheduleId={scheduleId ?? ''}
                  recognitionEvents={recognitionEvents}
                  liveCrops={liveCrops}
                />
              )}
            </div>
          </CardContent>
        </Card>

        <div className="flex flex-col gap-4 lg:min-h-[500px]">
          <AttendancePanel
            summary={latestSummary}
            isConnected={isConnected}
            onSelect={(userId) => selectTrack(null, userId)}
          />
          <div className="h-[420px]">
            <RecognitionPanel
              events={recognitionEvents}
              scheduleId={scheduleId ?? ''}
            />
          </div>
        </div>
      </div>

      {!isFullscreen && (
        <TrackDetailSheet
          latestFrame={latestFrame}
          latestSummary={latestSummary}
          isConnected={isConnected}
          scheduleId={scheduleId ?? ''}
          recognitionEvents={recognitionEvents}
          liveCrops={liveCrops}
        />
      )}
    </div>
  )
}
