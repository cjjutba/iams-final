import { create } from 'zustand'

/**
 * Which bbox / roster row is open in the live-feed TrackDetailSheet.
 *
 * Opening via a bbox click gives `trackId`; opening via an AttendancePanel row
 * gives only `userId`. `TrackDetailSheet` resolves whichever is set against
 * the latest WS `frame_update.tracks` list so both entry points feed the same
 * detail view.
 */
interface TrackSelectionState {
  selectedTrackId: number | null
  selectedUserId: string | null
  /** `performance.now()` when the sheet was opened — used for "Xs ago" labels. */
  openedAt: number | null
  select: (trackId: number | null, userId: string | null) => void
  clear: () => void
}

export const useTrackSelectionStore = create<TrackSelectionState>((set) => ({
  selectedTrackId: null,
  selectedUserId: null,
  openedAt: null,
  select: (trackId, userId) =>
    set({ selectedTrackId: trackId, selectedUserId: userId, openedAt: performance.now() }),
  clear: () => set({ selectedTrackId: null, selectedUserId: null, openedAt: null }),
}))
