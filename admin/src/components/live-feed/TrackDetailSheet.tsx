import { useEffect, useMemo, useRef, useState } from 'react'

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useRegisteredFaces } from '@/hooks/use-registered-faces'
import type { FrameUpdateMessage, TrackInfo } from '@/hooks/use-attendance-ws'
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
  videoElement: HTMLVideoElement | null
  videoSize: { width: number; height: number } | null
  isConnected: boolean
  activeStreamIsFallback: boolean
  scheduleId: string
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
  videoElement,
  videoSize,
  isConnected,
  activeStreamIsFallback,
  scheduleId,
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
  // The WHEP main stream on sub-profile is 640×360; on main fallback it's 2304×1296.
  // `activeStreamIsFallback` is true when the player fell back to main (i.e. sub
  // wasn't publishing), so the client crop is actually high-res in that case.
  const isSubStream = !activeStreamIsFallback

  // Phase 3: admin can toggle between the client-side canvas grab (Phase 1
  // path, always works even for unrecognized faces) and the server-side main-
  // profile crop (captured on the warming_up → recognized transition,
  // higher-resolution, but only exists for students the ML has already
  // matched this session). Default to client because it's always available
  // and matches the thesis-defense "show instantly when clicked" feel.
  const [cropSource, setCropSource] = useState<'client' | 'server'>('client')

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
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Live Crop
                </h3>
                <Tabs
                  value={cropSource}
                  onValueChange={(v) => setCropSource(v as 'client' | 'server')}
                >
                  <TabsList className="h-7">
                    <TabsTrigger value="client" className="px-2 text-[11px]">
                      Client
                    </TabsTrigger>
                    <TabsTrigger value="server" className="px-2 text-[11px]">
                      Server
                    </TabsTrigger>
                  </TabsList>
                  <TabsContent value="client" />
                  <TabsContent value="server" />
                </Tabs>
              </div>
              <LiveCropPanel
                source={
                  cropSource === 'client'
                    ? {
                        kind: 'client',
                        videoElement,
                        bbox: track?.bbox ?? null,
                        trackId: track?.track_id ?? selectedTrackId,
                        isStale,
                        isSubStream,
                      }
                    : {
                        kind: 'server',
                        scheduleId,
                        userId: effectiveUserId,
                      }
                }
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
