import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useTrackSelectionStore } from '@/stores/track-selection.store'

import { TrackDetailBody, type TrackDetailBodyProps } from './TrackDetailBody'

type Props = TrackDetailBodyProps

/**
 * Side-panel for the admin live-feed page. Opens when a bbox is clicked
 * (`OverlayClickTargets`) or an attendance row is clicked
 * (`AttendancePanel.onSelect`). The fullscreen view uses
 * `TrackDetailMiniPanel` instead — it renders inline inside the fullscreened
 * video container, since Radix Dialog portals to `document.body` and would be
 * invisible under the Fullscreen API.
 */
export function TrackDetailSheet(props: Props) {
  const { selectedTrackId, selectedUserId, clear } = useTrackSelectionStore()
  const isOpen = selectedTrackId !== null || selectedUserId !== null

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
        <SheetHeader className="sticky top-0 z-10 space-y-1 border-b bg-background/95 px-5 py-4 backdrop-blur supports-[backdrop-filter]:bg-background/80">
          <SheetTitle className="text-base">Face Comparison</SheetTitle>
          <SheetDescription className="text-[11.5px] text-muted-foreground">
            Registered angles vs. the live detection from the classroom camera.
          </SheetDescription>
        </SheetHeader>

        <TrackDetailBody {...props} />
      </SheetContent>
    </Sheet>
  )
}
