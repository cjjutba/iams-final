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
}

function AngleTile({ angle }: { angle: FaceAngleMetadata }) {
  const label = angle.angle_label ?? 'unknown'
  const quality =
    angle.quality_score !== null ? angle.quality_score.toFixed(2) : '—'

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

  return (
    <div className="flex flex-col gap-1 rounded-md border bg-muted/20 p-2">
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
        className="group relative flex aspect-square items-center justify-center overflow-hidden rounded bg-background/50 text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed"
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
            className="h-full w-full rounded object-cover -scale-x-100"
          />
        ) : revealed && loading ? (
          <Loader2 className="h-5 w-5 animate-spin opacity-50" aria-hidden />
        ) : revealed && error ? (
          <AlertTriangle
            className="h-5 w-5 opacity-50 text-amber-500"
            aria-hidden
          />
        ) : !hasImageUrl ? (
          // No image_url at all — Phase-1 metadata-only registrations.
          <Camera className="h-5 w-5 opacity-40" aria-hidden />
        ) : (
          // Hidden by default — show a muted privacy placeholder. Eye
          // icon hover overlay below indicates the click affordance.
          <EyeOff className="h-5 w-5 opacity-40" aria-hidden />
        )}

        {/* Hover overlay — only shown when there's something to toggle. */}
        {hasImageUrl && (
          <span
            className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition group-hover:bg-black/50 group-hover:opacity-100 group-focus-visible:bg-black/50 group-focus-visible:opacity-100"
            aria-hidden
          >
            {revealed ? (
              <EyeOff className="h-5 w-5 text-white" />
            ) : (
              <Eye className="h-5 w-5 text-white" />
            )}
          </span>
        )}
      </button>
      <div className="flex items-center justify-between text-[10px] uppercase tracking-wide">
        <span className="font-medium text-foreground">{label}</span>
        <TooltipProvider delayDuration={200}>
          <Tooltip>
            <TooltipTrigger asChild>
              <span
                className="cursor-help font-mono text-muted-foreground underline decoration-dotted decoration-muted-foreground/40 underline-offset-2"
                aria-label={`Quality score ${quality}`}
              >
                Q {quality}
              </span>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-[260px] text-xs normal-case tracking-normal">
              <p className="font-medium">Quality score (Laplacian variance)</p>
              <p className="mt-1 text-muted-foreground">
                Image sharpness measured at capture. Higher = sharper. Anything
                above ~30 indicates a clean registration that ArcFace can
                produce a stable embedding from. If a student fails to be
                recognized in class and their angles all show low Q, the
                registration is the weak link — re-register them in better
                lighting.
              </p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
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
export function RegisteredFaceGallery({ data }: Props) {
  if (data.status === 'idle' || data.status === 'loading') {
    return (
      <div className="grid grid-cols-3 gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="aspect-[3/4] w-full" />
        ))}
      </div>
    )
  }

  if (data.status === 'not-registered') {
    return (
      <div className="flex flex-col items-center gap-2 rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
        <UserX className="h-6 w-6" aria-hidden />
        <span>No face registration on file</span>
      </div>
    )
  }

  if (data.status === 'error') {
    return (
      <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-amber-500/40 p-6 text-center text-sm text-amber-600 dark:text-amber-500">
        <AlertTriangle className="h-6 w-6" aria-hidden />
        <span>Failed to load registration</span>
        <span className="text-xs text-muted-foreground">{data.message}</span>
      </div>
    )
  }

  const anyImages = data.angles.some((a) => a.image_url)
  const registered = data.registeredAt ? formatDateOnly(data.registeredAt) : null

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-3 gap-2">
        {data.angles.map((angle) => (
          <AngleTile key={angle.id} angle={angle} />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
        <Badge variant="outline" className="font-mono">
          {data.embeddingDim}-dim ArcFace
        </Badge>
        {registered && <span>Registered {registered}</span>}
        {!anyImages && (
          <span className="italic">Photos not yet persisted (Phase 2)</span>
        )}
      </div>
    </div>
  )
}
