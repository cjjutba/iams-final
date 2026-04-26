import { useMemo, useState } from 'react'
import { ScanFace, SlidersHorizontal, Video } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { useRegisteredFaces } from '@/hooks/use-registered-faces'
import { RegisteredFaceGallery } from '@/components/live-feed/RegisteredFaceGallery'
import type { FaceAngleMetadata, RegistrationData } from '@/types'
import { CctvCaptureGallery } from './CctvCaptureGallery'
import { DetectionHistoryList } from './DetectionHistoryList'

interface Props {
  userId: string
}

const PHONE_LABELS = new Set(['center', 'left', 'right', 'up', 'down'])

interface PartitionedAngles {
  phone: FaceAngleMetadata[]
  /** Map of room_key (e.g. "eb226") → ordered list of CCTV captures. */
  cctvByRoom: Map<string, FaceAngleMetadata[]>
  /** Pre-Phase-2 cctv_<idx> rows with no room context. */
  cctvLegacy: FaceAngleMetadata[]
}

/**
 * Split an angles list into phone angles + per-room CCTV captures.
 *
 * The backend returns every embedding the student has on file, mixed
 * together in one ``angles`` list (phone-domain ``center``/``left``/…
 * plus CCTV-domain ``cctv_eb226_<idx>`` / legacy ``cctv_<idx>``). The
 * Face Profile section presents them as separate groups so it's
 * obvious whether a room has working CCTV captures or whether the
 * student is operating off phone-domain selfies alone.
 */
function partitionAngles(angles: FaceAngleMetadata[]): PartitionedAngles {
  const phone: FaceAngleMetadata[] = []
  const cctvByRoom = new Map<string, FaceAngleMetadata[]>()
  const cctvLegacy: FaceAngleMetadata[] = []

  // Modern label format: cctv_<room_slug>_<idx>. The room slug is
  // alphanumeric + hyphen and may itself contain underscores in the
  // unlikely future case (build_cctv_label normalises room keys), so
  // we anchor on the trailing _<digits>$ to identify modern rows
  // and treat anything before that as the room key.
  const modernRe = /^cctv_(.+)_(\d+)$/
  const legacyRe = /^cctv_(\d+)$/

  for (const a of angles) {
    const label = a.angle_label
    if (!label) continue
    if (PHONE_LABELS.has(label)) {
      phone.push(a)
      continue
    }
    const legacy = legacyRe.exec(label)
    if (legacy) {
      cctvLegacy.push(a)
      continue
    }
    const modern = modernRe.exec(label)
    if (modern) {
      const roomKey = modern[1].toLowerCase()
      const bucket = cctvByRoom.get(roomKey) ?? []
      bucket.push(a)
      cctvByRoom.set(roomKey, bucket)
    }
    // Anything else (sim_eb226_v0, unknown labels) is filtered out —
    // those have no on-disk image and aren't user-meaningful.
  }

  // Stable sort within each bucket: by created_at ascending so the
  // operator sees captures in the order they were taken.
  const byCreated = (
    a: FaceAngleMetadata,
    b: FaceAngleMetadata,
  ) => a.created_at.localeCompare(b.created_at)
  phone.sort((a, b) => {
    // Preserve canonical phone order rather than chronological so
    // the Up/Center/Left/Right/Down row stays stable across views.
    const order = ['up', 'center', 'left', 'right', 'down']
    return (
      order.indexOf(a.angle_label ?? '') - order.indexOf(b.angle_label ?? '')
    )
  })
  for (const list of cctvByRoom.values()) list.sort(byCreated)
  cctvLegacy.sort(byCreated)

  return { phone, cctvByRoom, cctvLegacy }
}

/**
 * Wrap the partitioned phone angles back into a `RegistrationData`
 * shape so the existing `RegisteredFaceGallery` component can render
 * them without a refactor. CCTV captures get their own grid below.
 */
function phoneOnlyRegistrationData(
  source: RegistrationData,
  phone: FaceAngleMetadata[],
): RegistrationData {
  if (source.status !== 'ok') return source
  return { ...source, angles: phone }
}

/**
 * Two-column face profile rendered on the Student Record Detail page.
 *
 * Left column shows the registered face angles (5 once registration is
 * complete: UP / LEFT / RIGHT / CENTER / DOWN), followed by per-room
 * CCTV captures grouped under their room (e.g. EB226 — 5 captures).
 * Right column is the per-student slice of `recognition_events` —
 * paired probe crops + similarity scores for every FAISS decision
 * against this student, newest first.
 *
 * Quality scores ship behind a `Show diagnostics` toggle so normal
 * operators see soft Excellent/Good/Fair/Low buckets and ML-leaning
 * operators can flip the raw Laplacian-variance number on for
 * debugging.
 */
export function FaceVerificationCard({ userId }: Props) {
  const { data: registration } = useRegisteredFaces(userId)
  const [showDiagnostics, setShowDiagnostics] = useState(false)

  const partitioned = useMemo<PartitionedAngles>(() => {
    if (registration.status !== 'ok') {
      return { phone: [], cctvByRoom: new Map(), cctvLegacy: [] }
    }
    return partitionAngles(registration.angles)
  }, [registration])

  const phoneRegistration = useMemo(
    () => phoneOnlyRegistrationData(registration, partitioned.phone),
    [registration, partitioned.phone],
  )

  const totalCctv =
    Array.from(partitioned.cctvByRoom.values()).reduce(
      (a, b) => a + b.length,
      0,
    ) + partitioned.cctvLegacy.length

  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <ScanFace className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Face Profile</CardTitle>
          </div>
          <Label
            htmlFor="face-diagnostics-toggle"
            className="flex cursor-pointer items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
          >
            <SlidersHorizontal className="h-3 w-3" aria-hidden />
            Diagnostics
            <Switch
              id="face-diagnostics-toggle"
              checked={showDiagnostics}
              onCheckedChange={setShowDiagnostics}
              aria-label="Toggle ML diagnostics view"
            />
          </Label>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-6 md:grid-cols-2">
          <section className="flex flex-col gap-5">
            <div>
              <h4 className="mb-3 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Registered angles
              </h4>
              <RegisteredFaceGallery
                data={phoneRegistration}
                showDiagnostics={showDiagnostics}
              />
            </div>

            <div>
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <Video className="h-3.5 w-3.5 text-muted-foreground" />
                <h4 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  CCTV captures
                </h4>
                <Badge
                  variant="outline"
                  className="h-5 px-1.5 font-mono text-[10px] tabular-nums"
                >
                  {totalCctv}
                </Badge>
              </div>
              {totalCctv === 0 ? (
                <CctvEmptyState />
              ) : (
                <div className="flex flex-col gap-3">
                  {Array.from(partitioned.cctvByRoom.entries())
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([roomKey, captures]) => (
                      <CctvCaptureGallery
                        key={roomKey}
                        roomLabel={roomKey.toUpperCase()}
                        captures={captures}
                      />
                    ))}
                  {partitioned.cctvLegacy.length > 0 && (
                    <CctvCaptureGallery
                      key="_legacy"
                      roomLabel="Legacy"
                      captures={partitioned.cctvLegacy}
                      legacy
                    />
                  )}
                </div>
              )}
            </div>
          </section>

          <section>
            <h4 className="mb-3 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Recent detections
            </h4>
            <DetectionHistoryList studentId={userId} />
          </section>
        </div>
      </CardContent>
    </Card>
  )
}

function CctvEmptyState() {
  return (
    <div className="flex flex-col items-center gap-1.5 rounded-md border border-dashed bg-muted/20 p-4 text-center text-[11px] text-muted-foreground">
      <Video className="h-4 w-4 opacity-60" aria-hidden />
      <span>
        No CCTV captures yet. Run{' '}
        <span className="font-medium">CCTV Enrollment</span> to bridge the
        phone→camera domain gap for this student.
      </span>
    </div>
  )
}
