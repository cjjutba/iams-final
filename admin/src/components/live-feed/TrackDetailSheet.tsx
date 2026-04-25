import { useEffect, useMemo, useRef } from 'react'

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useRegisteredFaces } from '@/hooks/use-registered-faces'
import type {
  FrameUpdateMessage,
  RecognitionEventMessage,
  TrackInfo,
} from '@/hooks/use-attendance-ws'
import { useTrackSelectionStore } from '@/stores/track-selection.store'

import { RegisteredFaceGallery } from './RegisteredFaceGallery'
import { LiveCropPanel } from './LiveCropPanel'
import { SimilarityMetrics } from './SimilarityMetrics'

interface Props {
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
  // Same WS recognition-event stream the right-hand Recognition Stream
  // panel consumes. The Live Crop section picks the newest matching
  // event for the selected user so the image ticks forward instead of
  // freezing on the first captured frame. See use-server-side-crop.ts.
  recognitionEvents: RecognitionEventMessage[]
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
  summary: Props['latestSummary'],
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
 * Side-panel for the admin live-feed page. Opens when a bbox is clicked
 * (`OverlayClickTargets`) or an attendance row is clicked
 * (`AttendancePanel.onSelect`).
 *
 * Composes:
 *  - header: student name/ID + status chip
 *  - body: registered-angle gallery (left), live crop (right), metrics below
 *
 * Open/close state lives in `useTrackSelectionStore`. The track itself is
 * resolved from the latest WS `frame_update.tracks` against either the
 * selected `track_id` (bbox entry) or the `user_id` (roster entry) — so both
 * entry points feed the same view and the sheet stays open even when the
 * track briefly disappears from frame.
 */
export function TrackDetailSheet({
  latestFrame,
  latestSummary,
  isConnected,
  scheduleId,
  recognitionEvents,
}: Props) {
  const { selectedTrackId, selectedUserId, clear } = useTrackSelectionStore()
  const isOpen = selectedTrackId !== null || selectedUserId !== null

  const track = useMemo(
    () => resolveTrack(latestFrame, selectedTrackId, selectedUserId),
    [latestFrame, selectedTrackId, selectedUserId],
  )

  // When the bbox entry point gave us only a track_id and we resolve a
  // user_id from the WS frame, also reflect it in the store so the hooks that
  // need it can light up immediately (registered-faces fetch).
  useEffect(() => {
    if (!isOpen) return
    if (track?.user_id && selectedUserId !== track.user_id) {
      useTrackSelectionStore.getState().select(selectedTrackId, track.user_id)
    }
  }, [isOpen, track?.user_id, selectedTrackId, selectedUserId])

  const effectiveUserId = track?.user_id ?? selectedUserId
  const { data: registrationData } = useRegisteredFaces(effectiveUserId)
  const fallbackName = fallbackNameFromSummary(latestSummary, effectiveUserId)

  // Track when we last saw this track in the WS frame, for the "updated Xs
  // ago" label.
  const lastSeenAtRef = useRef<number | null>(null)
  useEffect(() => {
    if (track) lastSeenAtRef.current = performance.now()
  }, [track])

  // Reset lastSeen on selection change.
  useEffect(() => {
    lastSeenAtRef.current = null
  }, [selectedTrackId, selectedUserId])

  const isStale = isOpen && !track

  // Crop source is hard-pinned to "server" — the client-side canvas grab
  // (Phase 1) was admin-toggleable for a while, but operators consistently
  // chose Server (sharper crop from the main 2304×1296 stream, exact frame
  // the ML decided on) and the toggle just added confusion. The client
  // path still exists in `useLiveCrop` for any future caller that needs
  // sub-second crops for unrecognized tracks.
  return (
    <Sheet
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) clear()
      }}
    >
      <SheetContent
        side="right"
        className="flex w-full flex-col gap-0 overflow-y-auto sm:max-w-lg"
      >
        <SheetHeader>
          <SheetTitle>Face Comparison</SheetTitle>
          <SheetDescription>
            Registered angles vs. the live detection from the classroom camera.
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-4 px-4 pb-6">
          <SimilarityMetrics
            track={track}
            fallbackUserId={effectiveUserId}
            fallbackName={fallbackName}
            isConnected={isConnected}
            lastSeenAtMs={lastSeenAtRef.current}
            isStale={isStale}
          />

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <section className="flex flex-col gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Registered
              </h3>
              <RegisteredFaceGallery data={registrationData} />
            </section>

            <section className="flex flex-col gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Live Crop
              </h3>
              <LiveCropPanel
                source={{
                  kind: 'server',
                  scheduleId,
                  userId: effectiveUserId,
                  recognitionEvents,
                }}
              />
            </section>
          </div>

          <p className="text-[11px] leading-snug text-muted-foreground">
            Schedule <span className="font-mono">{scheduleId}</span>. Cosine
            similarity and matched identity come from the ML pipeline's FAISS
            lookup broadcast over the attendance WebSocket.
          </p>
        </div>
      </SheetContent>
    </Sheet>
  )
}
