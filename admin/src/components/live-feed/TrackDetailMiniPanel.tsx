import { X } from 'lucide-react'

import { useTrackSelectionStore } from '@/stores/track-selection.store'

import { TrackDetailBody, type TrackDetailBodyProps } from './TrackDetailBody'

type Props = TrackDetailBodyProps

/**
 * Inline face-comparison panel used in fullscreen mode. Slides in from the
 * right edge of the video container when a bbox or attendance row is selected.
 * Replaces `TrackDetailSheet` while fullscreen — Radix Dialog portals to
 * `document.body`, which is hidden by the Fullscreen API, so the Sheet would
 * be invisible. This component renders directly inside the fullscreened
 * container and never uses a portal, sidestepping that.
 */
export function TrackDetailMiniPanel(props: Props) {
  const { selectedTrackId, selectedUserId, clear } = useTrackSelectionStore()
  const isOpen = selectedTrackId !== null || selectedUserId !== null

  if (!isOpen) return null

  return (
    <div
      role="dialog"
      aria-label="Face comparison"
      className="pointer-events-auto absolute inset-y-0 right-0 z-30 flex w-full max-w-md flex-col overflow-hidden border-l border-border/40 bg-background/95 shadow-2xl backdrop-blur-md animate-in slide-in-from-right duration-200"
    >
      <div className="sticky top-0 z-10 flex items-start justify-between gap-2 border-b bg-background/95 px-5 py-4 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="space-y-1">
          <h2 className="text-base font-semibold">Face Comparison</h2>
          <p className="text-[11.5px] text-muted-foreground">
            Registered angles vs. the live detection from the classroom camera.
          </p>
        </div>
        <button
          type="button"
          onClick={clear}
          aria-label="Close face comparison"
          title="Close"
          className="-mr-1 -mt-1 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <TrackDetailBody {...props} />
      </div>
    </div>
  )
}
