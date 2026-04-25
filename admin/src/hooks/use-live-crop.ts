import { useClientSideCrop } from './use-client-side-crop'
import { useServerSideCrop } from './use-server-side-crop'
import type { RecognitionEventMessage } from './use-attendance-ws'
import type { LiveCropResult, LiveCropSource } from '@/types'

// Stable empty array reference for the `kind: 'client'` branch — keeps
// `useServerSideCrop`'s memo deps stable so React doesn't loop.
const EMPTY_EVENTS: RecognitionEventMessage[] = []

/**
 * Facade hook that dispatches to the right crop source.
 *
 * Phase 1 always feeds `{ kind: 'client', ... }`. Phase 3 flips the discriminator
 * at the call site in `TrackDetailSheet.tsx` to `{ kind: 'server', ... }`
 * without touching `LiveCropPanel`.
 *
 * Both branches hooks must be called unconditionally per React's rules — we
 * just hand one of them inert inputs based on the source kind.
 */
export function useLiveCrop(source: LiveCropSource): LiveCropResult {
  const isClient = source.kind === 'client'

  const clientResult = useClientSideCrop({
    videoElement: isClient ? source.videoElement : null,
    bbox: isClient ? source.bbox : null,
    trackId: isClient ? source.trackId : null,
    isStale: isClient ? source.isStale : false,
    isSubStream: isClient ? source.isSubStream : false,
  })

  const serverResult = useServerSideCrop({
    scheduleId: !isClient ? source.scheduleId : '',
    userId: !isClient ? source.userId : null,
    recognitionEvents: !isClient ? source.recognitionEvents : EMPTY_EVENTS,
  })

  return isClient ? clientResult : serverResult
}
