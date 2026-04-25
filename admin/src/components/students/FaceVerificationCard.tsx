import { useState } from 'react'
import { ScanFace, SlidersHorizontal } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { useRegisteredFaces } from '@/hooks/use-registered-faces'
import { RegisteredFaceGallery } from '@/components/live-feed/RegisteredFaceGallery'
import { DetectionHistoryList } from './DetectionHistoryList'

interface Props {
  userId: string
}

/**
 * Two-column face profile rendered on the Student Record Detail page.
 *
 * Left column shows the registered face angles (5 once registration is
 * complete: UP / LEFT / RIGHT / CENTER / DOWN). Right column is the
 * per-student slice of `recognition_events` — paired probe crops + similarity
 * scores for every FAISS decision against this student, newest first.
 *
 * Quality scores ship behind a `Show diagnostics` toggle so normal operators
 * see soft Excellent/Good/Fair/Low buckets and ML-leaning operators can flip
 * the raw Laplacian-variance number on for debugging.
 */
export function FaceVerificationCard({ userId }: Props) {
  const { data: registration } = useRegisteredFaces(userId)
  const [showDiagnostics, setShowDiagnostics] = useState(false)

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
          <section>
            <h4 className="mb-3 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Registered angles
            </h4>
            <RegisteredFaceGallery data={registration} showDiagnostics={showDiagnostics} />
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
