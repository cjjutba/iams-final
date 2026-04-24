import { ScanFace } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useRegisteredFaces } from '@/hooks/use-registered-faces'
import { RegisteredFaceGallery } from '@/components/live-feed/RegisteredFaceGallery'
import { DetectionHistoryList } from './DetectionHistoryList'

interface Props {
  userId: string
}

/**
 * Two-column verification card rendered on the Student Record Detail page.
 *
 * Left column shows the 5 registered face angles (always available once the
 * student has completed face registration). Right column is the per-student
 * slice of `recognition_events` — paired probe crops + similarity scores
 * for every FAISS decision, newest first.
 *
 * Phase A ships the left column + a placeholder on the right. Phase D wires
 * real recognition-event data once the capture pipeline is in place.
 */
export function FaceVerificationCard({ userId }: Props) {
  const { data: registration } = useRegisteredFaces(userId)

  return (
    <Card>
      <CardHeader className="flex flex-row items-center gap-2 pb-4">
        <ScanFace className="h-4 w-4 text-muted-foreground" />
        <CardTitle className="text-lg">Face Verification</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-6 md:grid-cols-2">
          <section>
            <h4 className="mb-3 text-sm font-medium text-muted-foreground">
              Registered angles
            </h4>
            <RegisteredFaceGallery data={registration} />
          </section>

          <section>
            <h4 className="mb-3 text-sm font-medium text-muted-foreground">
              Recent detections
            </h4>
            <DetectionHistoryList studentId={userId} />
          </section>
        </div>
      </CardContent>
    </Card>
  )
}
