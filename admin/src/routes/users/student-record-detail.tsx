import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { usePageTitle } from '@/hooks/use-page-title'
import { useBreadcrumbStore } from '@/stores/breadcrumb.store'
import { type ColumnDef } from '@tanstack/react-table'
import { safeFormat } from '@/lib/utils'
import { toast } from 'sonner'
import {
  ArrowLeft,
  Pencil,
  Phone,
  Mail,
  Calendar,
  IdCard,
  GraduationCap,
  ScanFace,
  UserX,
  Smartphone,
} from 'lucide-react'

import { DataTable } from '@/components/data-tables'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  useStudentRecord,
  useUpdateStudentRecord,
  useDeactivateStudentRecord,
  useUserAttendance,
  useDeregisterFace,
  useStudentEnrollments,
  useEnrollStudent,
  useUnenrollStudent,
  useSchedules,
} from '@/hooks/use-queries'
import type { AttendanceRecord } from '@/types'
import { formatStatus } from '@/types/attendance'
import { Loader2, Plus, Trash2, BookOpen } from 'lucide-react'

const statusBadgeVariant: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  present: 'default',
  late: 'secondary',
  absent: 'destructive',
  excused: 'outline',
  early_leave: 'destructive',
}

export default function StudentRecordDetailPage() {
  const { studentId } = useParams<{ studentId: string }>()
  const navigate = useNavigate()
  const setLabel = useBreadcrumbStore((s) => s.setLabel)

  const { data: student, isLoading } = useStudentRecord(studentId!)

  const fullName = student ? `${student.first_name} ${student.last_name}` : null
  usePageTitle(fullName ?? 'Student Details')

  useEffect(() => {
    if (fullName) setLabel(fullName)
    return () => setLabel(null)
  }, [fullName, setLabel])

  const { data: attendance = [], isLoading: attendanceLoading } = useUserAttendance(
    student?.user_id ?? '',
    !!student?.user_id,
  )

  const [editOpen, setEditOpen] = useState(false)
  const updateMutation = useUpdateStudentRecord()
  const deactivateMutation = useDeactivateStudentRecord()
  const deregisterMutation = useDeregisterFace()
  const actionLoading = deactivateMutation.isPending || deregisterMutation.isPending

  // Enrollment management
  const { data: enrollments = [], isLoading: enrollmentsLoading } = useStudentEnrollments(student?.user_id ?? '')
  const { data: allSchedules = [] } = useSchedules()
  const enrollMutation = useEnrollStudent()
  const unenrollMutation = useUnenrollStudent()
  const [enrollDialogOpen, setEnrollDialogOpen] = useState(false)
  const [unenrollConfirm, setUnenrollConfirm] = useState<{ scheduleId: string; name: string } | null>(null)

  const enrolledScheduleIds = new Set((enrollments as Array<{ schedule_id: string }>).map((e) => e.schedule_id))
  const availableSchedules = allSchedules.filter((s) => s.is_active && !enrolledScheduleIds.has(s.id))

  const [form, setForm] = useState({
    first_name: '',
    middle_name: '',
    last_name: '',
    email: '',
    course: '',
    year_level: '',
    section: '',
    birthdate: '',
    contact_number: '',
  })
  useEffect(() => {
    if (editOpen && student) {
      setForm({
        first_name: student.first_name,
        middle_name: student.middle_name ?? '',
        last_name: student.last_name,
        email: student.email ?? '',
        course: student.course ?? '',
        year_level: student.year_level ? String(student.year_level) : '',
        section: student.section ?? '',
        birthdate: student.birthdate ?? '',
        contact_number: student.contact_number ?? '',
      })
    }
  }, [editOpen, student])

  function handleChange(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleEditSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!student) return
    if (!form.first_name || !form.last_name) {
      toast.error('First name and last name are required.')
      return
    }
    try {
      await updateMutation.mutateAsync({
        studentId: student.student_id,
        data: {
          first_name: form.first_name,
          middle_name: form.middle_name || undefined,
          last_name: form.last_name,
          email: form.email || undefined,
          course: form.course || undefined,
          year_level: form.year_level ? Number(form.year_level) : undefined,
          section: form.section || undefined,
          birthdate: form.birthdate || undefined,
          contact_number: form.contact_number || undefined,
        },
      })
      toast.success(`${form.first_name} ${form.last_name} has been updated.`)
      setEditOpen(false)
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to update'
      const errorMsg = typeof msg === 'string' ? msg : JSON.stringify(msg)
      toast.error(errorMsg)
    }
  }

  const handleDeactivate = async () => {
    if (!student) return
    try {
      await deactivateMutation.mutateAsync(student.student_id)
      toast.success(`${student.first_name} ${student.last_name} has been deactivated.`)
      navigate('/students')
    } catch {
      toast.error('Failed to deactivate student record.')
    }
  }

  const handleDeregister = async () => {
    if (!student?.user_id) return
    try {
      await deregisterMutation.mutateAsync(student.user_id)
      toast.success(`Face data for ${student.first_name} ${student.last_name} has been removed.`)
    } catch {
      toast.error('Failed to deregister face.')
    }
  }

  const attendanceColumns: ColumnDef<AttendanceRecord>[] = [
    {
      accessorKey: 'date',
      header: 'Date',
      cell: ({ row }) => (
        <span className="text-sm">
          {safeFormat(row.original.date, 'MMM d, yyyy')}
        </span>
      ),
    },
    {
      accessorKey: 'subject_code',
      header: 'Subject',
      cell: ({ row }) => (
        <span className="text-sm">{row.original.subject_code ?? '\u2014'}</span>
      ),
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ row }) => (
        <Badge variant={statusBadgeVariant[row.original.status] ?? 'outline'}>
          {formatStatus(row.original.status)}
        </Badge>
      ),
    },
    {
      accessorKey: 'check_in_time',
      header: 'Check-in Time',
      cell: ({ row }) => (
        <span className="text-sm">
          {safeFormat(row.original.check_in_time, 'h:mm a')}
        </span>
      ),
    },
    {
      accessorKey: 'presence_score',
      header: 'Presence Score',
      cell: ({ row }) => (
        <span className="text-sm">{row.original.presence_score}%</span>
      ),
    },
  ]

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!student) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => navigate('/students')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Students
        </Button>
        <p className="text-muted-foreground">Student record not found.</p>
      </div>
    )
  }

  const initials = `${student.first_name.charAt(0)}${student.last_name.charAt(0)}`.toUpperCase()

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate('/students')}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Students
      </Button>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <Avatar className="h-16 w-16 text-lg">
                <AvatarFallback className="text-lg">{initials}</AvatarFallback>
              </Avatar>
              <div>
                <CardTitle className="text-xl">
                  {student.first_name}{' '}
                  {student.middle_name ? `${student.middle_name} ` : ''}
                  {student.last_name}
                </CardTitle>
                <div className="mt-1 flex items-center gap-2">
                  <Badge variant="default" className="capitalize">Student</Badge>
                  {student.is_active ? (
                    <Badge variant="default">Active</Badge>
                  ) : (
                    <Badge variant="destructive">Inactive</Badge>
                  )}
                  {student.is_registered ? (
                    <Badge variant="secondary">
                      <Smartphone className="mr-1 h-3 w-3" />
                      App Registered
                    </Badge>
                  ) : (
                    <Badge variant="outline">Not Registered</Badge>
                  )}
                  {student.has_face_registered && (
                    <Badge variant="secondary">
                      <ScanFace className="mr-1 h-3 w-3" />
                      Face Enrolled
                    </Badge>
                  )}
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </Button>
              {student.is_active && (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="outline" size="sm" disabled={actionLoading}>
                      <UserX className="mr-2 h-4 w-4" />
                      Deactivate
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Deactivate Student</AlertDialogTitle>
                      <AlertDialogDescription>
                        Are you sure you want to deactivate {student.first_name}{' '}
                        {student.last_name}? They will be removed from the active registry.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel disabled={actionLoading}>Cancel</AlertDialogCancel>
                      <AlertDialogAction onClick={handleDeactivate} disabled={actionLoading}>
                        {actionLoading ? 'Deactivating...' : 'Deactivate'}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
              {student.is_registered && student.has_face_registered && (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="outline" size="sm" disabled={actionLoading}>
                      <ScanFace className="mr-2 h-4 w-4" />
                      Deregister Face
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Deregister Face</AlertDialogTitle>
                      <AlertDialogDescription>
                        Are you sure you want to remove face registration data for{' '}
                        {student.first_name} {student.last_name}? They will need to
                        re-register their face to use the attendance system.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel disabled={actionLoading}>Cancel</AlertDialogCancel>
                      <AlertDialogAction onClick={handleDeregister} disabled={actionLoading}>
                        {actionLoading ? 'Removing...' : 'Deregister'}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
            </div>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="pt-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="flex items-center gap-3">
              <IdCard className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Student ID</p>
                <p className="text-sm font-medium font-mono">{student.student_id}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Mail className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Email</p>
                <p className="text-sm font-medium">{student.email ?? '\u2014'}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Phone className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Contact Number</p>
                <p className="text-sm font-medium">{student.contact_number ?? '\u2014'}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <GraduationCap className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Course</p>
                <p className="text-sm font-medium">
                  {[student.course, student.year_level ? `Year ${student.year_level}` : null, student.section ? `Section ${student.section}` : null]
                    .filter(Boolean)
                    .join(' \u2022 ') || '\u2014'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Birthdate</p>
                <p className="text-sm font-medium">
                  {safeFormat(student.birthdate, 'MMM d, yyyy')}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Added to Registry</p>
                <p className="text-sm font-medium">
                  {safeFormat(student.created_at, 'MMM d, yyyy')}
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {student.user_id && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-lg">
                <BookOpen className="h-5 w-5" />
                Enrolled Schedules ({(enrollments as unknown[]).length})
              </CardTitle>
              <Button size="sm" onClick={() => setEnrollDialogOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Enroll in Schedule
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {enrollmentsLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : (enrollments as unknown[]).length === 0 ? (
              <p className="text-sm text-muted-foreground">No enrollments yet.</p>
            ) : (
              <div className="space-y-2">
                {(enrollments as Array<{ enrollment_id: string; schedule_id: string; schedule: { id: string; subject_code: string; subject_name: string; day_of_week: number; start_time: string; end_time: string; faculty_name?: string | null } | null }>).map((e) => (
                  <div key={e.enrollment_id} className="flex items-center justify-between rounded-md border px-4 py-3">
                    <div className="cursor-pointer" onClick={() => e.schedule && navigate(`/schedules/${e.schedule.id}`)}>
                      <p className="text-sm font-medium">{e.schedule?.subject_code} - {e.schedule?.subject_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {e.schedule ? ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][e.schedule.day_of_week] : ''} {e.schedule?.start_time?.slice(0,5)} - {e.schedule?.end_time?.slice(0,5)}
                        {e.schedule?.faculty_name ? ` · ${e.schedule.faculty_name}` : ''}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => setUnenrollConfirm({
                        scheduleId: e.schedule_id,
                        name: `${e.schedule?.subject_code} - ${e.schedule?.subject_name}`,
                      })}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Unenroll Confirmation */}
      <AlertDialog open={!!unenrollConfirm} onOpenChange={(open) => !open && setUnenrollConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unenroll from schedule?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove {student.first_name} from <strong>{unenrollConfirm?.name}</strong>? This will remove their enrollment and any future attendance tracking for this schedule.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (unenrollConfirm && student.user_id) {
                  unenrollMutation.mutate(
                    { scheduleId: unenrollConfirm.scheduleId, studentUserId: student.user_id },
                    { onSuccess: () => { toast.success('Unenrolled successfully'); setUnenrollConfirm(null) } }
                  )
                }
              }}
            >
              Unenroll
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Enroll in Schedule Dialog */}
      <Dialog open={enrollDialogOpen} onOpenChange={setEnrollDialogOpen}>
        <DialogContent className="sm:max-w-md max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>Enroll in Schedule</DialogTitle>
            <DialogDescription>Select a schedule to enroll {student.first_name} in.</DialogDescription>
          </DialogHeader>
          <div className="max-h-[300px] overflow-y-auto space-y-1">
            {availableSchedules.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                {(enrollments as unknown[]).length > 0 ? 'Enrolled in all available schedules.' : 'No active schedules available.'}
              </p>
            ) : (
              availableSchedules.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between rounded-md border px-3 py-2 hover:bg-accent cursor-pointer"
                  onClick={() => {
                    if (!student.user_id) return
                    enrollMutation.mutate(
                      { scheduleId: s.id, studentUserId: student.user_id },
                      { onSuccess: () => toast.success(`Enrolled in ${s.subject_code}`) }
                    )
                  }}
                >
                  <div>
                    <p className="text-sm font-medium">{s.subject_code} - {s.subject_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][s.day_of_week]} {s.start_time?.slice(0,5)} - {s.end_time?.slice(0,5)}
                      {s.faculty_name ? ` · ${s.faculty_name}` : ''}
                    </p>
                  </div>
                  <Plus className="h-4 w-4 text-muted-foreground" />
                </div>
              ))
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEnrollDialogOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {student.is_registered && (
        <div>
          <h3 className="text-lg font-semibold mb-4">Attendance History</h3>
          <DataTable
            columns={attendanceColumns}
            data={attendance}
            isLoading={attendanceLoading}
            searchColumn="subject_code"
            searchPlaceholder="Search by subject..."
            borderless
          />
        </div>
      )}

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>Edit Student</DialogTitle>
            <DialogDescription>
              Update the details for {student.first_name} {student.last_name}.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleEditSubmit} className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="edit_student_id">Student ID</Label>
              <Input id="edit_student_id" value={student.student_id} disabled />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="edit_first_name">First Name *</Label>
                <Input
                  id="edit_first_name"
                  placeholder="Juan"
                  value={form.first_name}
                  onChange={(e) => handleChange('first_name', e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit_middle_name">Middle Name</Label>
                <Input
                  id="edit_middle_name"
                  placeholder="Santos"
                  value={form.middle_name}
                  onChange={(e) => handleChange('middle_name', e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit_last_name">Last Name *</Label>
                <Input
                  id="edit_last_name"
                  placeholder="Dela Cruz"
                  value={form.last_name}
                  onChange={(e) => handleChange('last_name', e.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="edit_email">Email</Label>
                <Input
                  id="edit_email"
                  type="email"
                  placeholder="juan@jrmsu.edu.ph"
                  value={form.email}
                  onChange={(e) => handleChange('email', e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit_birthdate">Birthdate</Label>
                <Input
                  id="edit_birthdate"
                  type="date"
                  value={form.birthdate}
                  onChange={(e) => handleChange('birthdate', e.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="edit_course">Course</Label>
                <Input
                  id="edit_course"
                  placeholder="BSCPE"
                  value={form.course}
                  onChange={(e) => handleChange('course', e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit_year_level">Year Level</Label>
                <Select
                  value={form.year_level}
                  onValueChange={(v) => handleChange('year_level', v)}
                >
                  <SelectTrigger id="edit_year_level">
                    <SelectValue placeholder="Select" />
                  </SelectTrigger>
                  <SelectContent>
                    {[1, 2, 3, 4, 5].map((y) => (
                      <SelectItem key={y} value={String(y)}>
                        {y}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit_section">Section</Label>
                <Input
                  id="edit_section"
                  placeholder="A"
                  value={form.section}
                  onChange={(e) => handleChange('section', e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="edit_contact_number">Contact Number</Label>
              <Input
                id="edit_contact_number"
                placeholder="09xxxxxxxxx"
                value={form.contact_number}
                onChange={(e) => handleChange('contact_number', e.target.value)}
              />
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditOpen(false)}
                disabled={updateMutation.isPending}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Save Changes'
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
