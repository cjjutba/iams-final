import { useState } from 'react'
import {
  UserX,
  Camera,
  AlertTriangle,
  Loader2,
  Eye,
  EyeOff,
} from 'lucide-react'

import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useAuthedImage } from '@/hooks/use-authed-image'
import { formatDateOnly } from '@/lib/format-time'
import type { RegistrationData, FaceAngleMetadata } from '@/types'

interface Props {
  data: RegistrationData
  /**
   * When true the per-tile footer shows the raw Laplacian-variance quality
   * score next to the angle label — useful for ML debugging but noise for
   * normal operators. Default false; the parent surfaces a "Show diagnostics"
   * toggle that flips this on.
   */
  showDiagnostics?: boolean
}

/** Coarse quality bucket — operators don't need the raw float. */
function bucketQuality(q: number | null): 'excellent' | 'good' | 'fair' | 'low' | 'unknown' {
  if (q == null) return 'unknown'
  // Laplacian-variance thresholds (empirical, see use-registered-faces.ts).
  // 80+ = excellent, 30-80 = good, 10-30 = fair, <10 = low. Above that
  // ArcFace embeddings are stable; below 10 the registration is the weak
  // link and a re-capture is recommended.
  if (q >= 80) return 'excellent'
  if (q >= 30) return 'good'
  if (q >= 10) return 'fair'
  return 'low'
}

const QUALITY_BUCKET_LABEL: Record<ReturnType<typeof bucketQuality>, string> = {
  excellent: 'Excellent',
  good: 'Good',
  fair: 'Fair',
  low: 'Low',
  unknown: '—',
}

const QUALITY_BUCKET_DOT: Record<ReturnType<typeof bucketQuality>, string> = {
  excellent: 'bg-emerald-500',
  good: 'bg-emerald-400',
  fair: 'bg-amber-500',
  low: 'bg-red-500',
  unknown: 'bg-muted-foreground/40',
}

function AngleTile({
  angle,
  showDiagnostics = false,
}: {
  angle: FaceAngleMetadata
  showDiagnostics?: boolean
}) {
  const label = angle.angle_label ?? 'unknown'
  const rawQuality =
    angle.quality_score !== null ? angle.quality_score.toFixed(2) : '—'
  const bucket = bucketQuality(angle.quality_score)

  // Privacy: registered face crops are hidden by default. The operator
  // explicitly clicks the eye to reveal each tile. We pass `null` to
  // useAuthedImage while hidden — that means we never even round-trip
  // the JPEG bytes from the backend until the operator opts in. Once
  // hidden again, the cached blob URL is released by the hook's cleanup.
  const [revealed, setRevealed] = useState(false)

  // Backend serves JPEGs at admin-protected
  // /api/v1/face/registrations/{user_id}/images/{angle_label}. Plain
  // ``<img src>`` can't attach the Bearer header → 401 → broken image.
  // useAuthedImage fetches via the authed Axios client and gives us a
  // blob URL the <img> can render same-origin.
  const { src, loading, error } = useAuthedImage(
    revealed ? angle.image_url : null,
  )

  const hasImageUrl = Boolean(angle.image_url)

  // Compact tile layout: image fills the square, a small colored dot in the
  // top-right corner conveys quality at a glance (full breakdown on hover).
  // Below the tile, just the angle label — centered, uppercase, truncated.
  // The previous layout tried to fit `LABEL ● Excellent` on a single ~50px
  // row and the words collided across adjacent tiles.
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <button
        type="button"
        onClick={() => {
          if (!hasImageUrl) return
          setRevealed((prev) => !prev)
        }}
        disabled={!hasImageUrl}
        aria-label={
          revealed
            ? `Hide ${label} angle`
            : `Reveal ${label} angle`
        }
        aria-pressed={revealed}
        className="group relative flex aspect-square items-center justify-center overflow-hidden rounded-md border border-border/60 bg-muted/40 text-muted-foreground transition-colors hover:border-border focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
      >
        {revealed && src ? (
          // Selfie captures from the student app are saved un-mirrored
          // (correct orientation for ArcFace, which trains on
          // un-mirrored faces). For the human reviewer that means a
          // "left angle" capture has the face pointing to the viewer's
          // RIGHT — counterintuitive. -scale-x-100 horizontally flips
          // the displayed image so the perceived direction matches the
          // angle label. ArcFace embeddings are unaffected — only the
          // pixels on screen are flipped, not the underlying file.
          <img
            src={src}
            alt={`${label} angle`}
            className="h-full w-full rounded-md object-cover -scale-x-100"
          />
        ) : revealed && loading ? (
          <Loader2 className="h-4 w-4 animate-spin opacity-50" aria-hidden />
        ) : revealed && error ? (
          <AlertTriangle
            className="h-4 w-4 opacity-60 text-amber-500"
            aria-hidden
          />
        ) : !hasImageUrl ? (
          // No image_url at all — Phase-1 metadata-only registrations.
          <Camera className="h-4 w-4 opacity-30" aria-hidden />
        ) : (
          // Hidden by default — show a muted privacy placeholder. Eye
          // icon hover overlay below indicates the click affordance.
          <EyeOff className="h-4 w-4 opacity-30" aria-hidden />
        )}

        {/* Quality indicator — a small colored dot in the top-right corner.
            Full quality bucket name and raw Laplacian-variance number are
            available in the tooltip. Ringed so it stays visible on both
            light placeholders and revealed photos. */}
        <TooltipProvider delayDuration={200}>
          <Tooltip>
            <TooltipTrigger asChild>
              <span
                className="absolute right-1 top-1 z-10 inline-flex cursor-help"
                aria-label={`Quality ${QUALITY_BUCKET_LABEL[bucket]}`}
              >
                <span
                  className={`h-2 w-2 rounded-full ring-2 ring-background/90 ${QUALITY_BUCKET_DOT[bucket]}`}
                  aria-hidden
                />
              </span>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-[260px] text-xs">
              <p className="font-medium">
                Capture quality:{' '}
                <span className="capitalize">{QUALITY_BUCKET_LABEL[bucket]}</span>
              </p>
              <p className="mt-1 text-muted-foreground">
                Laplacian variance at capture (raw {rawQuality}). Higher =
                sharper. Anything in the Good or Excellent band gives ArcFace a
                stable embedding. If a student fails to be recognised and all
                angles show Low or Fair, the registration is the weak link —
                re-register in better lighting.
              </p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        {/* Hover overlay — only shown when there's something to toggle. */}
        {hasImageUrl && (
          <span
            className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition group-hover:bg-black/50 group-hover:opacity-100 group-focus-visible:bg-black/50 group-focus-visible:opacity-100"
            aria-hidden
          >
            {revealed ? (
              <EyeOff className="h-4 w-4 text-white" />
            ) : (
              <Eye className="h-4 w-4 text-white" />
            )}
          </span>
        )}
      </button>
      <div className="flex min-w-0 flex-col items-center gap-0.5 px-0.5 text-center">
        <span
          className="block w-full truncate text-[10px] font-medium uppercase tracking-wider text-foreground/80"
          title={label}
        >
          {label}
        </span>
        {showDiagnostics && (
          <span className="block w-full truncate font-mono text-[9.5px] tabular-nums text-muted-foreground/80">
            {rawQuality}
          </span>
        )}
      </div>
    </div>
  )
}

/**
 * Registered-angle gallery for the face-comparison sheet.
 *
 * Phase 1: every `image_url` is null so each tile renders an icon-only
 * metadata card (angle label + quality score). Phase 2 populates `image_url`
 * server-side and the tile renders the JPEG — no component change.
 */
export function RegisteredFaceGallery({ data, showDiagnostics = false }: Props) {
  if (data.status === 'idle' || data.status === 'loading') {
    return (
      <div className="grid grid-cols-5 gap-1.5">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="aspect-square w-full rounded-md" />
        ))}
      </div>
    )
  }

  if (data.status === 'not-registered') {
    return (
      <div className="flex flex-col items-center gap-1.5 rounded-md border border-dashed bg-muted/20 p-5 text-center text-xs text-muted-foreground">
        <UserX className="h-5 w-5" aria-hidden />
        <span>No face registration on file</span>
      </div>
    )
  }

  if (data.status === 'error') {
    return (
      <div className="flex flex-col items-center gap-1.5 rounded-md border border-dashed border-amber-500/40 bg-amber-500/5 p-5 text-center text-xs text-amber-600 dark:text-amber-500">
        <AlertTriangle className="h-5 w-5" aria-hidden />
        <span className="font-medium">Failed to load registration</span>
        <span className="text-[11px] text-muted-foreground">{data.message}</span>
      </div>
    )
  }

  const anyImages = data.angles.some((a) => a.image_url)
  const registered = data.registeredAt ? formatDateOnly(data.registeredAt) : null
  // Single-row, exactly-as-many-columns-as-angles layout. Previously this
  // was grid-cols-3 with 5 angles, which produced a phantom empty cell in
  // the bottom-right that looked like a broken 6th tile (reported on the
  // student detail page redesign).
  const colsClass =
    data.angles.length >= 5 ? 'grid-cols-5'
      : data.angles.length === 4 ? 'grid-cols-4'
      : data.angles.length === 3 ? 'grid-cols-3'
      : data.angles.length === 2 ? 'grid-cols-2'
      : 'grid-cols-1'

  return (
    <div className="flex flex-col gap-3">
      <div className={`grid ${colsClass} gap-1.5`}>
        {data.angles.map((angle) => (
          <AngleTile key={angle.id} angle={angle} showDiagnostics={showDiagnostics} />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[10.5px] text-muted-foreground">
        <Badge
          variant="outline"
          className="h-5 px-1.5 font-mono text-[10px] tabular-nums"
        >
          {data.embeddingDim}d ArcFace
        </Badge>
        {registered && (
          <span>
            Registered <span className="text-foreground/70">{registered}</span>
          </span>
        )}
        {!anyImages && (
          <span className="italic text-muted-foreground/70">
            Photos not yet persisted
          </span>
        )}
      </div>
    </div>
  )
}
