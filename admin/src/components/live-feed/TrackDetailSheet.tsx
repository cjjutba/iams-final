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
  LiveCropUpdateMessage,
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
  // panel consumes. Used by the Live Crop section as a *fallback* when
  // no fast-lane broadcast has arrived for the selected user yet.
  recognitionEvents: RecognitionEventMessage[]
  // Latest live-display broadcast keyed by user_id, ~1 Hz fast lane
  // independent of the 10 s evidence-persistence throttle. The sheet
  // looks up the entry matching the currently selected user and hands
  // it to LiveCropPanel; the live broadcast wins over the slower
  // recognition_event fallback when present. See use-server-side-crop.
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
  liveCrops,
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
        className="flex w-full flex-col gap-0 overflow-y-auto p-0 sm:max-w-lg"
      >
        {/* Sticky header — keeps the sheet's identity anchored when the
            content scrolls. Padding lives here, not on SheetContent, so
            the sticky band can span the full width with a clean hairline. */}
        <SheetHeader className="sticky top-0 z-10 space-y-1 border-b bg-background/95 px-5 py-4 backdrop-blur supports-[backdrop-filter]:bg-background/80">
          <SheetTitle className="text-base">Face Comparison</SheetTitle>
          <SheetDescription className="text-[11.5px] text-muted-foreground">
            Registered angles vs. the live detection from the classroom camera.
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-5 px-5 pb-6 pt-4">
          <SimilarityMetrics
            track={track}
            fallbackUserId={effectiveUserId}
            fallbackName={fallbackName}
            isConnected={isConnected}
            lastSeenAtMs={lastSeenAtRef.current}
            isStale={isStale}
          />

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

          {/* Footer — schedule UUID truncated; full content available on
              hover/focus via title attribute. The boilerplate description
              that used to live here is in the sheet header now. */}
          <div
            className="mt-1 flex items-center gap-1.5 border-t pt-3 text-[10px] text-muted-foreground/70"
            title={`Schedule ${scheduleId}`}
          >
            <span className="uppercase tracking-wider">Schedule</span>
            <span className="font-mono tabular-nums">
              {scheduleId.slice(0, 8)}
            </span>
            <span className="ml-auto">via FAISS WebSocket</span>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}

/**
 * Section heading for the Registered / Live Crop columns. Centralised so
 * the typographic rhythm is identical and any future tweak is one edit.
 */
function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="px-0.5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
      {children}
    </h3>
  )
}
