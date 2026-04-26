import { useEffect, useMemo, useRef, type ReactNode } from 'react'

import { useRegisteredFaces } from '@/hooks/use-registered-faces'
import type {
  FrameUpdateMessage,
  LiveCropUpdateMessage,
  RecognitionEventMessage,
  TrackInfo,
} from '@/hooks/use-attendance-ws'
import { useTrackSelectionStore } from '@/stores/track-selection.store'

import { RegisteredFaceGallery } from './RegisteredFaceGallery'
import { LiveCropPanel } from './LiveCropPanel'
import { RecognitionDiagnostics } from './RecognitionDiagnostics'
import { SimilarityMetrics } from './SimilarityMetrics'

export interface TrackDetailBodyProps {
  latestFrame: FrameUpdateMessage | null
  latestSummary: {
    present?: Array<{ user_id: string; name: string }>
    late?: Array<{ user_id: string; name: string }>
    absent?: Array<{ user_id: string; name: string }>
    early_leave?: Array<{ user_id: string; name: string }>
    early_leave_returned?: Array<{ user_id: string; name: string }>
  } | null
  isConnected: boolean
  scheduleId: string
  recognitionEvents: RecognitionEventMessage[]
  liveCrops: Record<string, LiveCropUpdateMessage>
}

function resolveTrack(
  frame: FrameUpdateMessage | null,
  trackId: number | null,
  userId: string | null,
): TrackInfo | null {
  if (!frame) return null
  if (trackId !== null) {
    const byTrack = frame.tracks.find((t) => t.track_id === trackId)
    if (byTrack) return byTrack
  }
  if (userId) {
    const byUser = frame.tracks.find((t) => t.user_id === userId)
    if (byUser) return byUser
  }
  return null
}

function fallbackNameFromSummary(
  summary: TrackDetailBodyProps['latestSummary'],
  userId: string | null,
): string | null {
  if (!summary || !userId) return null
  const buckets: Array<Array<{ user_id: string; name: string }> | undefined> = [
    summary.present,
    summary.late,
    summary.absent,
    summary.early_leave,
    summary.early_leave_returned,
  ]
  for (const bucket of buckets) {
    if (!bucket) continue
    const hit = bucket.find((e) => e.user_id === userId)
    if (hit) return hit.name
  }
  return null
}

/**
 * Face-comparison body shared between `TrackDetailSheet` (off-canvas Sheet
 * mounted in normal page mode) and `TrackDetailMiniPanel` (inline overlay
 * inside the fullscreened video container). Owns the track resolution,
 * registered-face fetch, and lastSeen tracking — the wrappers are responsible
 * for the surrounding chrome (header / close affordance / animation shell).
 */
export function TrackDetailBody({
  latestFrame,
  latestSummary,
  isConnected,
  scheduleId,
  recognitionEvents,
  liveCrops,
}: TrackDetailBodyProps) {
  const { selectedTrackId, selectedUserId } = useTrackSelectionStore()
  const isOpen = selectedTrackId !== null || selectedUserId !== null

  const track = useMemo(
    () => resolveTrack(latestFrame, selectedTrackId, selectedUserId),
    [latestFrame, selectedTrackId, selectedUserId],
  )

  useEffect(() => {
    if (!isOpen) return
    if (track?.user_id && selectedUserId !== track.user_id) {
      useTrackSelectionStore.getState().select(selectedTrackId, track.user_id)
    }
  }, [isOpen, track?.user_id, selectedTrackId, selectedUserId])

  const effectiveUserId = track?.user_id ?? selectedUserId
  const { data: registrationData } = useRegisteredFaces(effectiveUserId)
  const fallbackName = fallbackNameFromSummary(latestSummary, effectiveUserId)

  const lastSeenAtRef = useRef<number | null>(null)
  useEffect(() => {
    if (track) lastSeenAtRef.current = performance.now()
  }, [track])

  useEffect(() => {
    lastSeenAtRef.current = null
  }, [selectedTrackId, selectedUserId])

  const isStale = isOpen && !track

  return (
    <div className="flex flex-col gap-5 px-5 pb-6 pt-4">
      <SimilarityMetrics
        track={track}
        fallbackUserId={effectiveUserId}
        fallbackName={fallbackName}
        isConnected={isConnected}
        lastSeenAtMs={lastSeenAtRef.current}
        isStale={isStale}
      />

      {/* Distant-face plan v2 (2026-04-26) — per-track recognition
          diagnostics so operators can see top-1 / top-2 / decision_reason
          inline without grepping dozzle. Renders nothing when track is
          null (initial open before WS data lands). */}
      <RecognitionDiagnostics track={track} />

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <section className="flex flex-col gap-2.5">
          <SectionHeading>Registered</SectionHeading>
          <RegisteredFaceGallery data={registrationData} />
        </section>

        <section className="flex flex-col gap-2.5">
          <SectionHeading>Live Crop</SectionHeading>
          <LiveCropPanel
            source={{
              kind: 'server',
              scheduleId,
              userId: effectiveUserId,
              recognitionEvents,
              liveCrop: effectiveUserId
                ? (liveCrops[effectiveUserId] ?? null)
                : null,
            }}
          />
        </section>
      </div>

      <div
        className="mt-1 flex items-center gap-1.5 border-t pt-3 text-[10px] text-muted-foreground/70"
        title={`Schedule ${scheduleId}`}
      >
        <span className="uppercase tracking-wider">Schedule</span>
        <span className="font-mono tabular-nums">{scheduleId.slice(0, 8)}</span>
        <span className="ml-auto">via FAISS WebSocket</span>
      </div>
    </div>
  )
}

function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h3 className="px-0.5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
      {children}
    </h3>
  )
}
