import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2, Play, Square, Video } from 'lucide-react'
import { toast } from 'sonner'

import { WhepPlayer, type WhepPlayerHandle } from '@/components/live-feed/WhepPlayer'
import { DetectionOverlay } from '@/components/live-feed/DetectionOverlay'
import { AttendancePanel } from '@/components/live-feed/AttendancePanel'
import { RecognitionPanel } from '@/components/live-feed/RecognitionPanel'
import { OverlayClickTargets } from '@/components/live-feed/OverlayClickTargets'
import { TrackDetailSheet } from '@/components/live-feed/TrackDetailSheet'
import { useAttendanceWs } from '@/hooks/use-attendance-ws'
import { useFrameAligner } from '@/hooks/use-frame-aligner'
import { useSchedule, useRoom, useSessionStartEligibility } from '@/hooks/use-queries'
import type { SessionEligibility, SessionEligibilityCode } from '@/services/presence.service'
import { usePageTitle } from '@/hooks/use-page-title'
import { useBreadcrumbStore } from '@/stores/breadcrumb.store'
import { useTrackSelectionStore } from '@/stores/track-selection.store'
import api from '@/services/api'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

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

  // The admin display pulls the camera SUB stream (e.g. `eb226-sub`), not the
  // MAIN stream that the ML pipeline decodes. Two reasons:
  //   1. The browser viewport is ~1280-wide — 2560×1440 is wasted bytes and
  //      decode cycles.
  //   2. Sharing the main stream between mediamtx → browser WHEP and
  //      mediamtx → api-gateway frame_grabber caused the WebRTC jitter
  //      buffer to drift over long sessions, making the feed feel laggy.
  // Sub paths are provisioned by scripts/iams-cam-relay.sh + the
  // `~^.+-sub$` path in deploy/mediamtx.onprem.yml.
  const displayStreamKey = useMemo(() => {
    return streamKey ? `${streamKey}-sub` : null
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

  const { isConnected, latestFrame, latestSummary, latestSessionEvent, recognitionEvents } = useAttendanceWs(scheduleId)

  const playerRef = useRef<WhepPlayerHandle>(null)
  const [videoSize, setVideoSize] = useState<{ width: number; height: number } | null>(null)
  const [activeStream, setActiveStream] = useState<{ key: string; isFallback: boolean } | null>(null)
  const handleActivePathChange = useCallback((key: string, isFallback: boolean) => {
    setActiveStream({ key, isFallback })
  }, [])

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
    return (
      <div className="flex flex-col gap-4 p-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
          <Skeleton className="aspect-video w-full" />
          <Skeleton className="h-[500px] w-full" />
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate(`/schedules/${scheduleId}`)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-xl font-semibold leading-tight">
              {schedule.subject_code} — {schedule.subject_name}
            </h1>
            <p className="text-sm text-muted-foreground">
              {room.name}{room.building ? ` · ${room.building}` : ''} · Stream: <span className="font-mono">{streamKey}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {sessionActive === true ? (
            <Button
              variant="outline"
              onClick={endSession}
              disabled={sessionLoading}
              className="gap-2"
            >
              {sessionLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
              End Session
            </Button>
          ) : (
            <Button
              onClick={startSession}
              disabled={startButtonDisabled}
              title={startButtonTitle}
              className="gap-2"
            >
              {sessionLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Start Session
            </Button>
          )}
        </div>
      </div>

      {/* Video + Overlay | Attendance Panel */}
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            <div className="relative aspect-video w-full bg-black">
              <WhepPlayer
                ref={playerRef}
                streamKey={displayStreamKey ?? streamKey}
                fallbackStreamKey={streamKey ?? undefined}
                className="h-full w-full"
                onVideoSize={(w, h) => setVideoSize({ width: w, height: h })}
                onActivePathChange={handleActivePathChange}
              />
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
            </div>
            {(latestFrame || activeStream?.isFallback) && (
              <div className="flex flex-wrap items-center gap-4 border-t px-4 py-2 text-xs text-muted-foreground">
                {latestFrame && (
                  <>
                    <span>
                      Backend FPS: <span className="font-mono">{(latestFrame.fps ?? 0).toFixed(1)}</span>
                    </span>
                    {latestFrame.processing_ms != null && (
                      <span>
                        Latency: <span className="font-mono">{latestFrame.processing_ms.toFixed(0)} ms</span>
                      </span>
                    )}
                    <span>
                      Tracks: <span className="font-mono">{latestFrame.tracks.length}</span>
                    </span>
                    {/*
                      Per-stage timing readout (added 2026-04-25, live-feed
                      plan Step 2a). Only renders when the backend
                      broadcasts the new fields — older builds quietly omit
                      them. ``det/embed/faiss/other`` ms tells the
                      operator at a glance which stage is eating the
                      per-frame budget; useful for verifying Step 2b's
                      CoreML re-export after deploy.
                    */}
                    {(latestFrame.det_ms != null ||
                      latestFrame.embed_ms != null ||
                      latestFrame.faiss_ms != null ||
                      latestFrame.other_ms != null) && (
                      <span className="font-mono opacity-80">
                        det:{(latestFrame.det_ms ?? 0).toFixed(0)} embed:
                        {(latestFrame.embed_ms ?? 0).toFixed(0)} faiss:
                        {(latestFrame.faiss_ms ?? 0).toFixed(0)} other:
                        {(latestFrame.other_ms ?? 0).toFixed(0)} ms
                      </span>
                    )}
                  </>
                )}
                {activeStream?.isFallback && (
                  <span className="ml-auto text-amber-600 dark:text-amber-500">
                    Sub stream unavailable — showing <span className="font-mono">{activeStream.key}</span> (main)
                  </span>
                )}
              </div>
            )}
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

      <TrackDetailSheet
        latestFrame={latestFrame}
        latestSummary={latestSummary}
        videoElement={playerRef.current?.videoElement ?? null}
        videoSize={videoSize}
        isConnected={isConnected}
        activeStreamIsFallback={activeStream?.isFallback ?? false}
        scheduleId={scheduleId ?? ''}
      />

      {sessionActive === false && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">Session not running</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            {eligibility && !eligibility.allowed ? (
              <>
                The video stream is live but attendance cannot be started right now.
                <span className="mt-1 block font-medium text-foreground">{eligibility.message}</span>
              </>
            ) : (
              <>
                The video stream is live but attendance is not being marked. Click{' '}
                <span className="font-medium text-foreground">Start Session</span> to begin presence tracking.
              </>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
