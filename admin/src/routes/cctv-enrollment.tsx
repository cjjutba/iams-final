import { useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  ArrowRightLeft,
  CameraIcon,
  CheckCircle2,
  Info,
  Loader2,
  RefreshCw,
  ScanFace,
  ScanLine,
  Users,
  XCircle,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { WhepPlayer } from '@/components/live-feed/WhepPlayer'
import { usePageTitle } from '@/hooks/use-page-title'
import {
  useCctvEnrollCommit,
  useCctvEnrollPreview,
  useCctvEnrollmentStatus,
  useCctvIdentify,
} from '@/hooks/use-cctv-enrollment'
import type {
  CctvEnrollCommitResult,
  CctvEnrollPreviewFace,
  CctvEnrollPreviewResult,
  CctvEnrollmentRoomOption,
  CctvEnrollmentStudent,
  CctvIdentifiedFace,
  CctvIdentifyResult,
} from '@/types'

type FilterMode = 'all' | 'missing' | 'has' | 'phone-only'
type WorkflowTab = 'scan' | 'manual'

interface ScanSnapshot {
  result: CctvIdentifyResult
  capturedAt: number
}

interface PreviewSnapshot {
  result: CctvEnrollPreviewResult
  capturedAt: number
}

export default function CctvEnrollmentPage() {
  usePageTitle('CCTV Bulk Enrollment')

  const statusQuery = useCctvEnrollmentStatus()
  const previewMut = useCctvEnrollPreview()
  const commitMut = useCctvEnrollCommit()
  const identifyMut = useCctvIdentify()

  // ── Selection state ─────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<WorkflowTab>('scan')
  const [selectedRoomKey, setSelectedRoomKey] = useState<string | null>(null)
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)
  // Default to 'all' so every registered student is reachable. The
  // 'missing'/'has'/'phone-only' filters are still one click away when
  // the operator wants to focus on a subset (e.g. orientation-week
  // batch enrollment).
  const [filterMode, setFilterMode] = useState<FilterMode>('all')
  // Per-(user, room) latest preview so swapping students doesn't blow
  // away the preview the operator just took for someone else.
  const [previewByKey, setPreviewByKey] = useState<
    Record<string, PreviewSnapshot>
  >({})
  // Most recent commit result for the selected student, surfaced inline
  // so the operator gets visual confirmation before auto-advance.
  const [lastCommit, setLastCommit] = useState<CctvEnrollCommitResult | null>(
    null,
  )
  // Latest scan-mode snapshot, scoped per room so switching rooms
  // doesn't carry over a stale identification.
  const [scanByRoom, setScanByRoom] = useState<Record<string, ScanSnapshot>>(
    {},
  )

  const data = statusQuery.data
  const rooms = useMemo(
    () =>
      (data?.room_options ?? []).filter(
        (r): r is CctvEnrollmentRoomOption => r.has_camera,
      ),
    [data?.room_options],
  )

  // Pick a default room (first one with a camera) once data lands.
  useEffect(() => {
    if (selectedRoomKey == null && rooms.length > 0) {
      setSelectedRoomKey(rooms[0].stream_key)
    }
  }, [rooms, selectedRoomKey])

  const selectedRoom = useMemo(
    () => rooms.find((r) => r.stream_key === selectedRoomKey) ?? null,
    [rooms, selectedRoomKey],
  )

  // ── Queue derivation ───────────────────────────────────────
  const queue = useMemo<CctvEnrollmentStudent[]>(() => {
    if (!data) return []
    const all = data.students
    if (!selectedRoomKey) return all
    return all.filter((s) => {
      const inRoomCount = s.per_room[selectedRoomKey] ?? 0
      switch (filterMode) {
        case 'missing':
          return inRoomCount === 0
        case 'has':
          return inRoomCount > 0
        case 'phone-only':
          return s.phone_only
        case 'all':
        default:
          return true
      }
    })
  }, [data, selectedRoomKey, filterMode])

  // Auto-select first student in queue when queue changes and the
  // current selection isn't in it. Avoids a stale "highlighted but
  // filtered out" row.
  useEffect(() => {
    if (queue.length === 0) {
      setSelectedUserId(null)
      return
    }
    if (!selectedUserId || !queue.find((s) => s.user_id === selectedUserId)) {
      setSelectedUserId(queue[0].user_id)
    }
  }, [queue, selectedUserId])

  const selectedStudent = useMemo(
    () => data?.students.find((s) => s.user_id === selectedUserId) ?? null,
    [data?.students, selectedUserId],
  )

  // Snapshot key used to scope previews to (user, room).
  const previewKey =
    selectedStudent && selectedRoomKey
      ? `${selectedStudent.user_id}::${selectedRoomKey}`
      : null
  const currentPreview = previewKey ? previewByKey[previewKey] ?? null : null

  // Reset commit message when the operator switches selection so the
  // green "5 added" banner doesn't carry over to the next student.
  useEffect(() => {
    setLastCommit(null)
  }, [selectedUserId, selectedRoomKey])

  // ── Actions ────────────────────────────────────────────────
  const handlePreview = async () => {
    if (!selectedStudent || !selectedRoom) return
    try {
      const result = await previewMut.mutateAsync({
        userId: selectedStudent.user_id,
        body: { room: selectedRoom.stream_key },
      })
      const key = `${selectedStudent.user_id}::${selectedRoom.stream_key}`
      setPreviewByKey((prev) => ({
        ...prev,
        [key]: { result, capturedAt: Date.now() },
      }))
      if (!result.ok) {
        toast.warning(result.message)
      }
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Preview failed — see console',
      )
    }
  }

  const handleCommit = async () => {
    if (!selectedStudent || !selectedRoom) return
    setLastCommit(null)
    try {
      const result = await commitMut.mutateAsync({
        userId: selectedStudent.user_id,
        body: {
          room_code_or_id: selectedRoom.stream_key,
          num_captures: 5,
          capture_interval_s: 1.0,
        },
      })
      setLastCommit(result)
      toast.success(
        `Added ${result.added} CCTV captures for ${selectedStudent.full_name}`,
      )
      // Auto-advance to next student in queue after a brief pause so the
      // operator can read the success state. The status query has been
      // invalidated by the mutation hook; the queue will refresh and the
      // current student will likely drop out (no longer "missing").
      setTimeout(() => {
        const remaining = queue.filter(
          (s) => s.user_id !== selectedStudent.user_id,
        )
        if (remaining.length > 0) {
          setSelectedUserId(remaining[0].user_id)
        }
      }, 1500)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Commit failed'
      toast.error(msg)
    }
  }

  // Scan-mode handler — grabs one frame and identifies every face
  // against every enrolled student. Snapshot is keyed by room so
  // switching rooms doesn't show stale identifications.
  const handleScan = async () => {
    if (!selectedRoom) return
    try {
      const result = await identifyMut.mutateAsync({
        room: selectedRoom.stream_key,
      })
      setScanByRoom((prev) => ({
        ...prev,
        [selectedRoom.stream_key]: { result, capturedAt: Date.now() },
      }))
      if (!result.ok) {
        toast.warning(result.message)
      }
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Scan failed — see console',
      )
    }
  }

  // Per-face enroll from the scan grid — runs the existing 5-capture
  // commit endpoint for the identified student. The status query is
  // invalidated by the mutation hook so the per-face card re-renders
  // with the updated capture count.
  const handleScanEnroll = async (userId: string, fullName: string) => {
    if (!selectedRoom) return
    try {
      const result = await commitMut.mutateAsync({
        userId,
        body: {
          room_code_or_id: selectedRoom.stream_key,
          num_captures: 5,
          capture_interval_s: 1.0,
        },
      })
      toast.success(
        `Added ${result.added} CCTV captures for ${fullName}`,
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Enroll failed')
    }
  }

  const currentScan =
    selectedRoomKey != null ? scanByRoom[selectedRoomKey] ?? null : null

  // ── Render ─────────────────────────────────────────────────
  if (statusQuery.isLoading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (statusQuery.isError) {
    return (
      <div className="flex h-[60vh] flex-col items-center justify-center gap-2 text-muted-foreground">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <span>Failed to load CCTV enrollment status.</span>
        <Button variant="outline" onClick={() => statusQuery.refetch()}>
          Retry
        </Button>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="flex flex-col gap-6 pb-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">CCTV Bulk Enrollment</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Capture in-domain CCTV embeddings for each student × room.
            Works in a busy classroom: the system auto-picks the face
            that best matches the selected student's phone registration,
            so other people in frame are ignored.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => statusQuery.refetch()}
          disabled={statusQuery.isFetching}
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${statusQuery.isFetching ? 'animate-spin' : ''}`}
          />
          Refresh
        </Button>
      </div>

      {/* Room selection + global stats — shared by both tabs */}
      <Card>
        <CardContent className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs uppercase tracking-wide text-muted-foreground">
              Room
            </label>
            <Select
              value={selectedRoomKey ?? ''}
              onValueChange={(v) => setSelectedRoomKey(v)}
            >
              <SelectTrigger className="h-9 w-44">
                <SelectValue placeholder="Pick a room" />
              </SelectTrigger>
              <SelectContent>
                {rooms.length === 0 && (
                  <SelectItem value="__none__" disabled>
                    No camera-equipped rooms
                  </SelectItem>
                )}
                {rooms.map((r) => (
                  <SelectItem key={r.stream_key} value={r.stream_key}>
                    {r.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="ml-auto flex items-center gap-3 text-sm text-muted-foreground">
            <span>
              <span className="font-mono">{data.total_registered}</span>{' '}
              registered
            </span>
            <span>·</span>
            <span>
              <span className="font-mono">{data.phone_only_count}</span>{' '}
              phone-only
            </span>
            <span>·</span>
            <span>
              threshold{' '}
              <span className="font-mono">
                {(data.threshold * 100).toFixed(0)}%
              </span>{' '}
              / phone-only{' '}
              <span className="font-mono">
                {(data.phone_only_threshold * 100).toFixed(0)}%
              </span>
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Workflow tabs: Scan Classroom (camera-first) vs Manual Pick (queue-first) */}
      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as WorkflowTab)}
        className="gap-4"
      >
        <TabsList>
          <TabsTrigger value="scan">
            <ScanLine className="h-4 w-4" />
            Scan Classroom
          </TabsTrigger>
          <TabsTrigger value="manual">
            <Users className="h-4 w-4" />
            Manual Pick
          </TabsTrigger>
        </TabsList>

        <TabsContent value="scan" className="flex flex-col gap-4">
          <ScanClassroomPanel
            room={selectedRoom}
            scan={currentScan}
            scanBusy={identifyMut.isPending}
            commitBusy={commitMut.isPending}
            commitTargetUserId={
              commitMut.isPending && commitMut.variables
                ? commitMut.variables.userId
                : null
            }
            onScan={handleScan}
            onEnrollFace={handleScanEnroll}
          />
        </TabsContent>

        <TabsContent value="manual" className="flex flex-col gap-4">
          {/* Manual workflow filter (queue-only) */}
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs uppercase tracking-wide text-muted-foreground">
                Filter
              </label>
              <Select
                value={filterMode}
                onValueChange={(v) => setFilterMode(v as FilterMode)}
              >
                <SelectTrigger className="h-9 w-56">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">
                    All registered students
                  </SelectItem>
                  <SelectItem value="missing">
                    Missing in this room
                  </SelectItem>
                  <SelectItem value="has">
                    Has captures in this room
                  </SelectItem>
                  <SelectItem value="phone-only">
                    Phone-only (any room)
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Workflow hint */}
          <div className="flex gap-2 rounded-md border border-blue-200 bg-blue-50/60 p-3 text-xs text-blue-900 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-300">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <strong>How this works:</strong> Pick a student, then aim
              the camera at the room. The system detects every face in
              frame and auto-selects the one whose embedding best matches
              that student's existing phone registration. Other people in
              the shot are scored, shown for transparency, and ignored.
              Use <em>Preview Capture</em> to see what the system would
              pick before committing 5 frames to FAISS.
            </div>
          </div>

          {/* Two-pane: queue (left) + work area (right) */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[20rem_1fr]">
            <QueuePanel
              queue={queue}
              selectedRoomKey={selectedRoomKey}
              selectedUserId={selectedUserId}
              onSelect={setSelectedUserId}
            />
            <WorkPanel
              student={selectedStudent}
              room={selectedRoom}
              preview={currentPreview}
              lastCommit={lastCommit}
              previewBusy={previewMut.isPending}
              commitBusy={commitMut.isPending}
              onPreview={handlePreview}
              onCommit={handleCommit}
              onSwitchStudent={(uid) => setSelectedUserId(uid)}
              allStudents={data.students}
            />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

// ─── Queue ───────────────────────────────────────────────────

function QueuePanel({
  queue,
  selectedRoomKey,
  selectedUserId,
  onSelect,
}: {
  queue: CctvEnrollmentStudent[]
  selectedRoomKey: string | null
  selectedUserId: string | null
  onSelect: (uid: string) => void
}) {
  return (
    <Card className="overflow-hidden py-0">
      <CardHeader className="border-b py-4">
        <CardTitle className="text-sm">Queue ({queue.length})</CardTitle>
        <CardDescription className="text-xs">
          {queue.length === 0
            ? 'No students match the current filter.'
            : 'Click a student, have them stand in front of the camera, then preview & commit.'}
        </CardDescription>
      </CardHeader>
      <ScrollArea className="h-[36rem]">
        <ul className="divide-y">
          {queue.map((s) => {
            const inRoom =
              selectedRoomKey != null
                ? (s.per_room[selectedRoomKey] ?? 0)
                : 0
            const isSelected = s.user_id === selectedUserId
            return (
              <li key={s.user_id}>
                <button
                  type="button"
                  onClick={() => onSelect(s.user_id)}
                  className={`flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/50 ${
                    isSelected ? 'bg-muted' : ''
                  }`}
                >
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate text-sm font-medium">
                      {s.full_name || '(no name)'}
                    </span>
                    <span className="truncate text-xs text-muted-foreground">
                      {s.student_id ?? '—'}
                    </span>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {inRoom > 0 ? (
                      <Badge
                        variant="outline"
                        className="border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400"
                      >
                        {inRoom} captured
                      </Badge>
                    ) : (
                      <Badge variant="secondary">missing</Badge>
                    )}
                  </div>
                </button>
              </li>
            )
          })}
        </ul>
      </ScrollArea>
    </Card>
  )
}

// ─── Work area ───────────────────────────────────────────────

function WorkPanel({
  student,
  room,
  preview,
  lastCommit,
  previewBusy,
  commitBusy,
  onPreview,
  onCommit,
  onSwitchStudent,
  allStudents,
}: {
  student: CctvEnrollmentStudent | null
  room: CctvEnrollmentRoomOption | null
  preview: PreviewSnapshot | null
  lastCommit: CctvEnrollCommitResult | null
  previewBusy: boolean
  commitBusy: boolean
  onPreview: () => void
  onCommit: () => void
  onSwitchStudent: (userId: string) => void
  allStudents: CctvEnrollmentStudent[]
}) {
  if (!student || !room) {
    return (
      <Card className="flex h-[36rem] items-center justify-center">
        <CardContent className="text-center text-sm text-muted-foreground">
          {!room
            ? 'Select a camera-equipped room to begin.'
            : 'Select a student from the queue.'}
        </CardContent>
      </Card>
    )
  }

  const totalCaptures = Object.values(student.per_room).reduce(
    (a, b) => a + b,
    0,
  )

  return (
    <div className="flex flex-col gap-4">
      {/* Selected student summary */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{student.full_name}</CardTitle>
          <CardDescription>
            {student.student_id ?? '(no student ID)'} · {totalCaptures} CCTV
            captures total
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2">
          {Object.entries(student.per_room).map(([roomKey, count]) => (
            <Badge
              key={roomKey}
              variant="outline"
              className={
                roomKey === room.stream_key
                  ? 'border-primary text-primary'
                  : ''
              }
            >
              {roomKey.toUpperCase()}: {count}
            </Badge>
          ))}
          {(student.per_room[room.stream_key] ?? 0) === 0 && (
            <Badge variant="secondary">{room.stream_key.toUpperCase()}: 0</Badge>
          )}
          {student.cctv_legacy > 0 && (
            <Badge variant="outline">legacy: {student.cctv_legacy}</Badge>
          )}
          {student.phone_only && (
            <Badge variant="destructive">phone-only</Badge>
          )}
        </CardContent>
      </Card>

      {/* Live video + preview side-by-side on lg, stacked on smaller */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_22rem]">
        {/* WHEP video */}
        <Card className="overflow-hidden py-0">
          <CardHeader className="border-b py-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <CameraIcon className="h-4 w-4" />
              Live · {room.name}
            </CardTitle>
            <CardDescription className="text-xs">
              Have the student stand alone in front of the camera so only
              their face is visible.
            </CardDescription>
          </CardHeader>
          <div className="aspect-video w-full">
            <WhepPlayer
              streamKey={`${room.stream_key}-sub`}
              fallbackStreamKey={room.stream_key}
              className="h-full w-full"
            />
          </div>
        </Card>

        {/* Preview + actions */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Preview & Commit</CardTitle>
            <CardDescription className="text-xs">
              Preview grabs one frame and sanity-checks identity. Commit
              writes 5 captures to FAISS over ~5s.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <PreviewBox preview={preview} />

            <SwitchSuggestion
              preview={preview}
              currentStudentId={student.user_id}
              allStudents={allStudents}
              onSwitchStudent={onSwitchStudent}
            />

            <div className="flex flex-col gap-2">
              <Button
                variant="outline"
                onClick={onPreview}
                disabled={previewBusy || commitBusy}
              >
                {previewBusy ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Capturing preview…
                  </>
                ) : (
                  <>
                    <ScanFace className="mr-2 h-4 w-4" />
                    Preview Capture
                  </>
                )}
              </Button>
              {(() => {
                const bestSim =
                  preview?.result.best_self_similarity_to_phone ?? null
                const previewBlocks =
                  preview != null &&
                  (!preview.result.ok || (bestSim ?? 1) < 0.2)
                const isDisabled = commitBusy || previewBusy || previewBlocks
                return (
                  <>
                    <Button
                      onClick={onCommit}
                      disabled={isDisabled}
                      variant={previewBlocks ? 'outline' : 'default'}
                    >
                      {commitBusy ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Capturing 5 frames…
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="mr-2 h-4 w-4" />
                          Commit 5 Captures
                        </>
                      )}
                    </Button>
                    {previewBlocks && (
                      <p className="flex items-start gap-1.5 text-xs text-destructive">
                        <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        <span>
                          Commit blocked: best face in the latest preview
                          {bestSim != null
                            ? ` only matches at sim ${(bestSim * 100).toFixed(0)}%`
                            : ' could not be scored'}
                          . The selected student is not in frame.
                          Re-preview after they arrive, or switch to the
                          right student.
                        </span>
                      </p>
                    )}
                    {preview == null && (
                      <p className="text-xs text-muted-foreground">
                        Tip: take a Preview first to confirm the right
                        student is in frame. Commit will work without one
                        but won't catch a wrong-person mistake before
                        writing.
                      </p>
                    )}
                  </>
                )
              })()}
            </div>

            {lastCommit && (
              <CommitResultBox result={lastCommit} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function PreviewBox({ preview }: { preview: PreviewSnapshot | null }) {
  if (preview == null) {
    return (
      <div className="flex h-44 items-center justify-center rounded-md border border-dashed text-xs text-muted-foreground">
        No preview yet
      </div>
    )
  }
  const { result } = preview
  const ageS = Math.max(0, Math.floor((Date.now() - preview.capturedAt) / 1000))
  const bestSim = result.best_self_similarity_to_phone
  // Header status reflects the best face's sim band, not the overall ok
  // flag, so the operator sees "low confidence" even when capture
  // technically succeeded.
  const headerOk = result.ok && bestSim != null && bestSim >= 0.3
  return (
    <div className="rounded-md border">
      <div className="flex items-center gap-2 border-b px-3 py-2">
        {headerOk ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
        ) : result.ok ? (
          <AlertCircle className="h-4 w-4 text-amber-500" />
        ) : (
          <XCircle className="h-4 w-4 text-destructive" />
        )}
        <span className="text-xs font-medium">
          {result.ok
            ? `${result.face_count} face${result.face_count === 1 ? '' : 's'} detected`
            : 'No usable face'}
        </span>
        {bestSim != null && (
          <span className="font-mono text-[11px] text-muted-foreground">
            best sim:{' '}
            <span
              className={
                bestSim >= 0.5
                  ? 'text-emerald-600'
                  : bestSim >= 0.3
                    ? 'text-amber-600'
                    : 'text-destructive'
              }
            >
              {(bestSim * 100).toFixed(1)}%
            </span>
          </span>
        )}
        <span className="ml-auto text-[10px] text-muted-foreground">
          {ageS}s ago
        </span>
      </div>
      <p className="px-3 py-2 text-xs text-muted-foreground">
        {result.message}
      </p>
      {result.faces.length > 0 && (
        <ul className="space-y-2 border-t px-3 py-3">
          {result.faces.map((f, i) => (
            <PreviewFaceRow key={i} face={f} />
          ))}
        </ul>
      )}
    </div>
  )
}

function PreviewFaceRow({ face }: { face: CctvEnrollPreviewFace }) {
  const sim = face.self_similarity_to_phone
  const simClass =
    sim >= 0.5
      ? 'text-emerald-600'
      : sim >= 0.3
        ? 'text-amber-600'
        : 'text-destructive'
  // Cross-id label: when we have a confident global best-match (>=0.40)
  // for this face, show whose face it actually is. This is what makes
  // multi-face frames legible — operator can see "yes that's Christian"
  // even when the selected student is somebody else entirely.
  const crossId =
    face.best_match_user_id &&
    face.best_match_full_name &&
    face.best_match_sim != null &&
    face.best_match_sim >= 0.4
      ? `${face.best_match_full_name} (${(face.best_match_sim * 100).toFixed(0)}%)`
      : null
  return (
    <li
      className={`flex items-start gap-3 rounded-md border p-2 ${
        face.is_best_match
          ? 'border-primary/60 bg-primary/5'
          : 'border-transparent'
      }`}
    >
      <div className="h-16 w-16 shrink-0 overflow-hidden rounded border bg-muted">
        <img
          src={`data:image/jpeg;base64,${face.crop_b64}`}
          alt="Detected face"
          className="h-full w-full object-cover"
        />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1 text-[11px]">
        <div className="flex items-center gap-2">
          {face.is_best_match ? (
            <Badge
              variant="outline"
              className="border-primary text-primary"
            >
              auto-selected
            </Badge>
          ) : (
            <Badge variant="secondary">other face</Badge>
          )}
          <span className={`font-mono ${simClass}`}>
            sim {(sim * 100).toFixed(1)}%
          </span>
          <span className="font-mono text-muted-foreground">
            det {(face.det_score * 100).toFixed(0)}%
          </span>
          <span className="font-mono text-muted-foreground">
            {face.bbox[2]}×{face.bbox[3]}px
          </span>
        </div>
        {crossId && (
          <span className="text-muted-foreground">
            Identified as <span className="font-medium">{crossId}</span>
          </span>
        )}
        {!face.is_best_match && !crossId && (
          <span className="text-muted-foreground">
            Ignored — not the best match for the selected student.
          </span>
        )}
      </div>
    </li>
  )
}

/**
 * "Did you mean to enroll [Other Student]?" card.
 *
 * Surfaces when the system's auto-selected face for the current
 * student-in-queue actually best-matches a different enrolled
 * student. Catches the operator-error case where the wrong student is
 * selected in the queue (e.g. queue has Desiree but Christian is in
 * front of the camera) before any captures land in FAISS.
 *
 * Trigger conditions (all required):
 *  - Preview returned a best-match face
 *  - That face's best_match_user_id is NOT the currently-selected student
 *  - That face's best_match_sim is high enough to be a confident
 *    cross-id (>= 0.40 — well above the 0.30 "plausible" band, well
 *    below the 0.70 "definitive" zone, room for false positives but
 *    operator confirms with one click)
 *  - The suggested student is in the operator's queue (so they CAN
 *    switch — e.g. not a faculty member who happened to walk past)
 */
function SwitchSuggestion({
  preview,
  currentStudentId,
  allStudents,
  onSwitchStudent,
}: {
  preview: PreviewSnapshot | null
  currentStudentId: string
  allStudents: CctvEnrollmentStudent[]
  onSwitchStudent: (userId: string) => void
}) {
  if (!preview || preview.result.faces.length === 0) return null
  const best = preview.result.faces.find((f) => f.is_best_match)
  if (!best) return null

  const suggestedId = best.best_match_user_id
  const suggestedSim = best.best_match_sim
  if (
    !suggestedId ||
    suggestedSim == null ||
    suggestedSim < 0.4 ||
    suggestedId === currentStudentId
  ) {
    return null
  }

  const suggestedStudent = allStudents.find((s) => s.user_id === suggestedId)
  if (!suggestedStudent) return null

  return (
    <div className="rounded-md border border-amber-300 bg-amber-50/80 p-3 dark:border-amber-800 dark:bg-amber-950/30">
      <div className="flex items-start gap-2">
        <ArrowRightLeft className="mt-0.5 h-4 w-4 shrink-0 text-amber-700 dark:text-amber-400" />
        <div className="flex-1 text-xs">
          <p className="font-medium text-amber-900 dark:text-amber-300">
            This face appears to be{' '}
            <span className="font-semibold">{suggestedStudent.full_name}</span>{' '}
            (sim {(suggestedSim * 100).toFixed(0)}%), not the selected student.
          </p>
          <p className="mt-1 text-amber-800 dark:text-amber-400">
            Switch to enroll them instead, or call the correct student to
            the camera.
          </p>
        </div>
      </div>
      <Button
        size="sm"
        variant="outline"
        className="mt-2 w-full border-amber-400 bg-white text-amber-900 hover:bg-amber-100 dark:bg-amber-950/60 dark:text-amber-200 dark:hover:bg-amber-900/40"
        onClick={() => onSwitchStudent(suggestedId)}
      >
        <ArrowRightLeft className="mr-2 h-3.5 w-3.5" />
        Switch to {suggestedStudent.full_name}
      </Button>
    </div>
  )
}

// ─── Scan Classroom Panel (camera-first workflow) ────────────

function ScanClassroomPanel({
  room,
  scan,
  scanBusy,
  commitBusy,
  commitTargetUserId,
  onScan,
  onEnrollFace,
}: {
  room: CctvEnrollmentRoomOption | null
  scan: ScanSnapshot | null
  scanBusy: boolean
  commitBusy: boolean
  commitTargetUserId: string | null
  onScan: () => void
  onEnrollFace: (userId: string, fullName: string) => void
}) {
  if (!room) {
    return (
      <Card className="flex h-[24rem] items-center justify-center">
        <CardContent className="text-center text-sm text-muted-foreground">
          Select a camera-equipped room to begin scanning.
        </CardContent>
      </Card>
    )
  }

  return (
    <>
      {/* Scan-mode help banner */}
      <div className="flex gap-2 rounded-md border border-blue-200 bg-blue-50/60 p-3 text-xs text-blue-900 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-300">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <strong>How this works:</strong> Aim the camera at the room
          and click <em>Scan Frame Now</em>. The system detects every
          face, identifies each one against the registered students, and
          shows them as cards. Click <em>Enroll for {room.name}</em> on
          any face that still needs CCTV captures — no need to pick a
          student from a queue first.
        </div>
      </div>

      {/* Live video + scan trigger */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_22rem]">
        <Card className="overflow-hidden py-0">
          <CardHeader className="border-b py-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <CameraIcon className="h-4 w-4" />
              Live · {room.name}
            </CardTitle>
            <CardDescription className="text-xs">
              Single frame is captured when you click scan; live video is
              just for framing.
            </CardDescription>
          </CardHeader>
          <div className="aspect-video w-full">
            <WhepPlayer
              streamKey={`${room.stream_key}-sub`}
              fallbackStreamKey={room.stream_key}
              className="h-full w-full"
            />
          </div>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Scan</CardTitle>
            <CardDescription className="text-xs">
              Grabs one frame and identifies every face in it. Re-scan
              after students move into position.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Button onClick={onScan} disabled={scanBusy}>
              {scanBusy ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Scanning…
                </>
              ) : (
                <>
                  <ScanLine className="mr-2 h-4 w-4" />
                  Scan Frame Now
                </>
              )}
            </Button>
            {scan && (
              <ScanSummary scan={scan} />
            )}
          </CardContent>
        </Card>
      </div>

      {/* Identified faces grid */}
      {scan && scan.result.faces.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">
              Detected faces ({scan.result.face_count})
            </CardTitle>
            <CardDescription className="text-xs">
              {scan.result.identified_count} identified ·{' '}
              {scan.result.face_count - scan.result.identified_count}{' '}
              unknown. Click <em>Enroll</em> to capture 5 CCTV frames for
              that student in {room.name}.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {scan.result.faces.map((face, i) => (
                <ScanFaceCard
                  key={i}
                  face={face}
                  room={room}
                  commitBusy={
                    commitBusy &&
                    !!face.identified_user_id &&
                    commitTargetUserId === face.identified_user_id
                  }
                  globalCommitBusy={commitBusy}
                  onEnroll={() =>
                    face.identified_user_id &&
                    face.identified_full_name &&
                    onEnrollFace(
                      face.identified_user_id,
                      face.identified_full_name,
                    )
                  }
                />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {scan && scan.result.faces.length === 0 && (
        <div className="flex flex-col items-center gap-2 rounded-md border border-dashed py-12 text-sm text-muted-foreground">
          <ScanFace className="h-6 w-6" />
          <span>{scan.result.message}</span>
        </div>
      )}

      {!scan && !scanBusy && (
        <div className="flex flex-col items-center gap-2 rounded-md border border-dashed py-16 text-sm text-muted-foreground">
          <ScanLine className="h-6 w-6" />
          <span>
            Click <em>Scan Frame Now</em> to identify everyone in front
            of the camera.
          </span>
        </div>
      )}
    </>
  )
}

function ScanSummary({ scan }: { scan: ScanSnapshot }) {
  const ageS = Math.max(0, Math.floor((Date.now() - scan.capturedAt) / 1000))
  return (
    <div className="rounded-md border bg-muted/40 p-3 text-xs">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
        <span className="font-medium">{scan.result.message}</span>
        <span className="ml-auto text-[10px] text-muted-foreground">
          {ageS}s ago
        </span>
      </div>
      {scan.result.frame_size && (
        <div className="mt-1 font-mono text-[10px] text-muted-foreground">
          frame {scan.result.frame_size[0]}×{scan.result.frame_size[1]}
        </div>
      )}
    </div>
  )
}

function ScanFaceCard({
  face,
  room,
  commitBusy,
  globalCommitBusy,
  onEnroll,
}: {
  face: CctvIdentifiedFace
  room: CctvEnrollmentRoomOption
  commitBusy: boolean
  globalCommitBusy: boolean
  onEnroll: () => void
}) {
  const isIdentified = !!face.identified_user_id
  const inRoomCount = face.per_room[room.stream_key] ?? 0
  const sim = face.identified_sim
  const simClass =
    sim != null
      ? sim >= 0.6
        ? 'text-emerald-600'
        : sim >= 0.4
          ? 'text-amber-600'
          : 'text-destructive'
      : 'text-muted-foreground'

  return (
    <div className="flex flex-col overflow-hidden rounded-md border">
      {/* Crop */}
      <div className="aspect-square w-full overflow-hidden bg-muted">
        <img
          src={`data:image/jpeg;base64,${face.crop_b64}`}
          alt={face.identified_full_name ?? 'Detected face'}
          className="h-full w-full object-cover"
        />
      </div>
      {/* Identification */}
      <div className="flex flex-col gap-1 border-t p-3">
        {isIdentified ? (
          <>
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-medium">
                {face.identified_full_name}
              </span>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <span className="font-mono">
                {face.identified_student_id ?? '—'}
              </span>
              <span>·</span>
              <span className={`font-mono ${simClass}`}>
                sim {((sim ?? 0) * 100).toFixed(0)}%
              </span>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              {Object.entries(face.per_room).map(([roomKey, count]) => (
                <Badge
                  key={roomKey}
                  variant="outline"
                  className={
                    roomKey === room.stream_key
                      ? 'border-primary text-primary'
                      : ''
                  }
                >
                  {roomKey.toUpperCase()}: {count}
                </Badge>
              ))}
              {inRoomCount === 0 && (
                <Badge variant="secondary">
                  {room.stream_key.toUpperCase()}: 0
                </Badge>
              )}
            </div>
          </>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4 text-muted-foreground" />
              <span className="truncate text-sm font-medium">Unknown</span>
            </div>
            <p className="text-[11px] text-muted-foreground">
              No registered student matched this face above the
              identification threshold. Either not enrolled yet, or
              framing/lighting hurts recognition.
            </p>
          </>
        )}
      </div>
      {/* Action */}
      <div className="border-t p-2">
        <Button
          size="sm"
          className="w-full"
          variant={face.already_enrolled_in_room ? 'outline' : 'default'}
          disabled={!isIdentified || globalCommitBusy}
          onClick={onEnroll}
        >
          {commitBusy ? (
            <>
              <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
              Capturing 5 frames…
            </>
          ) : !isIdentified ? (
            <>
              <XCircle className="mr-2 h-3.5 w-3.5" />
              Cannot enroll (unknown)
            </>
          ) : face.already_enrolled_in_room ? (
            <>
              <CheckCircle2 className="mr-2 h-3.5 w-3.5" />
              Re-enroll for {room.name}
            </>
          ) : (
            <>
              <ScanFace className="mr-2 h-3.5 w-3.5" />
              Enroll for {room.name}
            </>
          )}
        </Button>
      </div>
    </div>
  )
}

function CommitResultBox({ result }: { result: CctvEnrollCommitResult }) {
  const meanPct = (result.self_similarity_to_phone_mean * 100).toFixed(1)
  const minPct = (result.self_similarity_to_phone_min * 100).toFixed(1)
  const maxPct = (result.self_similarity_to_phone_max * 100).toFixed(1)
  return (
    <div className="rounded-md border border-emerald-200 bg-emerald-50/60 p-3 dark:border-emerald-900 dark:bg-emerald-950/30">
      <div className="flex items-center gap-2 text-sm font-medium text-emerald-700 dark:text-emerald-400">
        <CheckCircle2 className="h-4 w-4" />
        Added {result.added} captures
      </div>
      <div className="mt-1 font-mono text-[11px] text-muted-foreground">
        sim → phone: mean {meanPct}% · min {minPct}% · max {maxPct}%
      </div>
      <div className="mt-1 font-mono text-[11px] text-muted-foreground">
        labels: {result.labels.join(', ')}
      </div>
      {Object.keys(result.skipped_reasons).length > 0 && (
        <div className="mt-1 text-[11px] text-muted-foreground">
          skipped:{' '}
          {Object.entries(result.skipped_reasons)
            .map(([k, v]) => `${k}=${v}`)
            .join(', ')}
        </div>
      )}
    </div>
  )
}
