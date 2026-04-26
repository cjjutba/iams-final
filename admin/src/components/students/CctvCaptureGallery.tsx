import { useState } from 'react'
import {
  AlertTriangle,
  Camera,
  Eye,
  EyeOff,
  Loader2,
  Video,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { useAuthedImage } from '@/hooks/use-authed-image'
import type { FaceAngleMetadata } from '@/types'

interface Props {
  /** Display label for the room (e.g. "EB226"). */
  roomLabel: string
  captures: FaceAngleMetadata[]
  /**
   * True when these captures came from the pre-Phase-2 single-namespace
   * `cctv_<idx>` rows. Surfaced as a small "legacy" badge so operators
   * understand why a row has no room context.
   */
  legacy?: boolean
}

/**
 * One row of CCTV-domain face captures for a student × room.
 *
 * Used by `FaceVerificationCard` to render a separate gallery per
 * room (EB226 / EB227 / Legacy), parallel to the phone-angle gallery
 * above. Each tile is privacy-gated behind a click — exactly like the
 * phone gallery — so registered face crops never auto-load on the
 * student detail page.
 */
export function CctvCaptureGallery({ roomLabel, captures, legacy }: Props) {
  const withImages = captures.filter((c) => c.image_url)
  const withoutImages = captures.length - withImages.length

  return (
    <div className="rounded-md border bg-muted/10 p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Video className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-[11px] font-semibold uppercase tracking-wide">
          {roomLabel}
        </span>
        <Badge
          variant="outline"
          className="h-4 px-1.5 font-mono text-[10px] tabular-nums"
        >
          {captures.length} captured
        </Badge>
        {legacy && (
          <Badge
            variant="secondary"
            className="h-4 px-1.5 text-[10px] uppercase tracking-wide"
          >
            legacy
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-5 gap-1.5">
        {captures.map((c) => (
          <CctvTile key={c.id} capture={c} />
        ))}
      </div>

      {withoutImages > 0 && (
        <p className="mt-2 text-[10px] italic text-muted-foreground/80">
          {withoutImages} capture{withoutImages === 1 ? '' : 's'} missing on
          disk — most likely enrolled before image storage was wired up.
          Re-enroll via the CCTV Enrollment page to populate the thumbnails.
        </p>
      )}
    </div>
  )
}

function CctvTile({ capture }: { capture: FaceAngleMetadata }) {
  const [revealed, setRevealed] = useState(false)
  const { src, loading, error } = useAuthedImage(
    revealed ? capture.image_url : null,
  )

  const hasImageUrl = Boolean(capture.image_url)
  // Pull the trailing _<digits> off the label for a compact tile caption
  // like "#0", "#3" — saves horizontal space vs the full angle_label.
  const idx = capture.angle_label?.match(/_(\d+)$/)?.[1] ?? '?'

  return (
    <div className="flex min-w-0 flex-col gap-1">
      <button
        type="button"
        onClick={() => {
          if (!hasImageUrl) return
          setRevealed((p) => !p)
        }}
        disabled={!hasImageUrl}
        aria-label={
          revealed
            ? `Hide capture #${idx}`
            : hasImageUrl
              ? `Reveal capture #${idx}`
              : `Capture #${idx} has no stored image`
        }
        aria-pressed={revealed}
        className="group relative flex aspect-square items-center justify-center overflow-hidden rounded border border-border/60 bg-muted/40 text-muted-foreground transition-colors hover:border-border focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
      >
        {revealed && src ? (
          // CCTV crops are stored un-mirrored (correct orientation for
          // the recognition pipeline). Unlike phone selfies, no flip is
          // needed — these came from the camera directly.
          <img
            src={src}
            alt={`Capture #${idx}`}
            className="h-full w-full object-cover"
          />
        ) : revealed && loading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin opacity-50" aria-hidden />
        ) : revealed && error ? (
          <AlertTriangle
            className="h-3.5 w-3.5 text-amber-500 opacity-60"
            aria-hidden
          />
        ) : !hasImageUrl ? (
          <Camera className="h-3.5 w-3.5 opacity-30" aria-hidden />
        ) : (
          <EyeOff className="h-3.5 w-3.5 opacity-30" aria-hidden />
        )}

        {hasImageUrl && (
          <span
            className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition group-hover:bg-black/50 group-hover:opacity-100 group-focus-visible:bg-black/50 group-focus-visible:opacity-100"
            aria-hidden
          >
            {revealed ? (
              <EyeOff className="h-3.5 w-3.5 text-white" />
            ) : (
              <Eye className="h-3.5 w-3.5 text-white" />
            )}
          </span>
        )}
      </button>
      <span
        className="block truncate text-center font-mono text-[9.5px] uppercase tracking-wide text-muted-foreground"
        title={capture.angle_label ?? ''}
      >
        #{idx}
      </span>
    </div>
  )
}
