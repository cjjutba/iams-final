import { UserX, Camera, AlertTriangle } from 'lucide-react'

import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import type { RegistrationData, FaceAngleMetadata } from '@/types'

interface Props {
  data: RegistrationData
}

function AngleTile({ angle }: { angle: FaceAngleMetadata }) {
  const label = angle.angle_label ?? 'unknown'
  const quality =
    angle.quality_score !== null ? angle.quality_score.toFixed(2) : '—'

  return (
    <div className="flex flex-col gap-1 rounded-md border bg-muted/20 p-2">
      <div className="flex aspect-square items-center justify-center rounded bg-background/50 text-muted-foreground">
        {angle.image_url ? (
          <img
            src={angle.image_url}
            alt={`${label} angle`}
            className="h-full w-full rounded object-cover"
            loading="lazy"
          />
        ) : (
          <Camera className="h-5 w-5 opacity-50" aria-hidden />
        )}
      </div>
      <div className="flex items-center justify-between text-[10px] uppercase tracking-wide">
        <span className="font-medium text-foreground">{label}</span>
        <span className="font-mono text-muted-foreground">Q {quality}</span>
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
  const registered =
    data.registeredAt
      ? new Date(data.registeredAt).toLocaleDateString(undefined, {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        })
      : null

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
