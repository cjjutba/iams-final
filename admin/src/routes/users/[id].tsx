import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { format } from 'date-fns'
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  UserX,
  UserCheck,
  ScanFace,
  Phone,
  Mail,
  Calendar,
  IdCard,
} from 'lucide-react'
import { toast } from 'sonner'

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
import { usersService } from '@/services/users.service'
import { faceService } from '@/services/face.service'
import { attendanceService } from '@/services/attendance.service'
import type { UserResponse, UserRole, AttendanceRecord } from '@/types'

const roleBadgeVariant: Record<UserRole, 'default' | 'secondary' | 'outline'> = {
  student: 'default',
  faculty: 'secondary',
  admin: 'outline',
}

const statusBadgeVariant: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  PRESENT: 'default',
  LATE: 'secondary',
  ABSENT: 'destructive',
  EXCUSED: 'outline',
  EARLY_LEAVE: 'destructive',
}

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [user, setUser] = useState<UserResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [attendance, setAttendance] = useState<AttendanceRecord[]>([])
  const [attendanceLoading, setAttendanceLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)

  const fetchUser = useCallback(async () => {
    if (!id) return
    setIsLoading(true)
    try {
      const data = await usersService.getById(id)
      setUser(data)
    } catch {
      toast.error('Failed to load user.')
    } finally {
      setIsLoading(false)
    }
  }, [id])

  const fetchAttendance = useCallback(async () => {
    if (!id || !user || user.role !== 'student') return
    setAttendanceLoading(true)
    try {
      const data = await attendanceService.list({ student_id: id })
      setAttendance(data)
    } catch {
      toast.error('Failed to load attendance history.')
    } finally {
      setAttendanceLoading(false)
    }
  }, [id, user])

  useEffect(() => {
    void fetchUser()
  }, [fetchUser])

  useEffect(() => {
    void fetchAttendance()
  }, [fetchAttendance])

  const handleDeactivate = async () => {
    if (!user) return
    setActionLoading(true)
    try {
      await usersService.deactivate(user.id)
      toast.success(`${user.first_name} ${user.last_name} has been deactivated.`)
      await fetchUser()
    } catch {
      toast.error('Failed to deactivate user.')
    } finally {
      setActionLoading(false)
    }
  }

  const handleReactivate = async () => {
    if (!user) return
    setActionLoading(true)
    try {
      await usersService.reactivate(user.id)
      toast.success(`${user.first_name} ${user.last_name} has been reactivated.`)
      await fetchUser()
    } catch {
      toast.error('Failed to reactivate user.')
    } finally {
      setActionLoading(false)
    }
  }

  const handleDeregister = async () => {
    if (!user) return
    setActionLoading(true)
    try {
      await faceService.deregister(user.id)
      toast.success(`Face data for ${user.first_name} ${user.last_name} has been removed.`)
    } catch {
      toast.error('Failed to deregister face.')
    } finally {
      setActionLoading(false)
    }
  }

  const attendanceColumns: ColumnDef<AttendanceRecord>[] = [
    {
      accessorKey: 'date',
      header: 'Date',
      cell: ({ row }) => (
        <span className="text-sm">
          {format(new Date(row.original.date), 'MMM d, yyyy')}
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
          {row.original.status}
        </Badge>
      ),
    },
    {
      accessorKey: 'check_in_time',
      header: 'Check-in Time',
      cell: ({ row }) => (
        <span className="text-sm">
          {row.original.check_in_time
            ? format(new Date(row.original.check_in_time), 'h:mm a')
            : '\u2014'}
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

  if (!user) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => navigate('/users')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Users
        </Button>
        <p className="text-muted-foreground">User not found.</p>
      </div>
    )
  }

  const initials = `${user.first_name.charAt(0)}${user.last_name.charAt(0)}`.toUpperCase()

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate('/users')}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Users
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
                  {user.first_name} {user.last_name}
                </CardTitle>
                <div className="mt-1 flex items-center gap-2">
                  <Badge variant={roleBadgeVariant[user.role]} className="capitalize">
                    {user.role}
                  </Badge>
                  {user.is_active ? (
                    <Badge variant="default">Active</Badge>
                  ) : (
                    <Badge variant="destructive">Inactive</Badge>
                  )}
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              {user.is_active ? (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="outline" size="sm" disabled={actionLoading}>
                      <UserX className="mr-2 h-4 w-4" />
                      Deactivate
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Deactivate User</AlertDialogTitle>
                      <AlertDialogDescription>
                        Are you sure you want to deactivate {user.first_name}{' '}
                        {user.last_name}? They will no longer be able to access the
                        system.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel disabled={actionLoading}>
                        Cancel
                      </AlertDialogCancel>
                      <AlertDialogAction
                        onClick={handleDeactivate}
                        disabled={actionLoading}
                      >
                        {actionLoading ? 'Deactivating...' : 'Deactivate'}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              ) : (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="outline" size="sm" disabled={actionLoading}>
                      <UserCheck className="mr-2 h-4 w-4" />
                      Reactivate
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Reactivate User</AlertDialogTitle>
                      <AlertDialogDescription>
                        Are you sure you want to reactivate {user.first_name}{' '}
                        {user.last_name}? They will regain access to the system.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel disabled={actionLoading}>
                        Cancel
                      </AlertDialogCancel>
                      <AlertDialogAction
                        onClick={handleReactivate}
                        disabled={actionLoading}
                      >
                        {actionLoading ? 'Reactivating...' : 'Reactivate'}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}

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
                      {user.first_name} {user.last_name}? They will need to
                      re-register their face to use the attendance system.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel disabled={actionLoading}>
                      Cancel
                    </AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleDeregister}
                      disabled={actionLoading}
                    >
                      {actionLoading ? 'Removing...' : 'Deregister'}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="pt-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex items-center gap-3">
              <Mail className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Email</p>
                <p className="text-sm font-medium">{user.email}</p>
              </div>
            </div>
            {user.student_id && (
              <div className="flex items-center gap-3">
                <IdCard className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">Student ID</p>
                  <p className="text-sm font-medium">{user.student_id}</p>
                </div>
              </div>
            )}
            <div className="flex items-center gap-3">
              <Phone className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Phone</p>
                <p className="text-sm font-medium">{user.phone ?? '\u2014'}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Created</p>
                <p className="text-sm font-medium">
                  {format(new Date(user.created_at), 'MMM d, yyyy')}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {user.email_verified ? (
                <CheckCircle2 className="h-4 w-4 text-green-600" />
              ) : (
                <XCircle className="h-4 w-4 text-red-500" />
              )}
              <div>
                <p className="text-sm text-muted-foreground">Email Verified</p>
                <p className="text-sm font-medium">
                  {user.email_verified ? 'Verified' : 'Not verified'}
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Attendance History</CardTitle>
        </CardHeader>
        <CardContent>
          {user.role !== 'student' ? (
            <p className="text-sm text-muted-foreground">
              Attendance history is only available for students.
            </p>
          ) : (
            <DataTable
              columns={attendanceColumns}
              data={attendance}
              isLoading={attendanceLoading}
              searchColumn="subject_code"
              searchPlaceholder="Search by subject..."
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
