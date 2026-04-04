import { useEffect, useState } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { usePageTitle } from '@/hooks/use-page-title'
import { useBreadcrumbStore } from '@/stores/breadcrumb.store'
import { type ColumnDef } from '@tanstack/react-table'
import { format } from 'date-fns'
import {
  ArrowLeft,
  CheckCircle2,
  Loader2,
  XCircle,
  UserX,
  UserCheck,
  ScanFace,
  Pencil,
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
} from '@/components/ui/alert-dialog'
import {
  useUser,
  useUserAttendance,
  useDeactivateUser,
  useReactivateUser,
  useDeregisterFace,
} from '@/hooks/use-queries'
import type { UserRole, AttendanceRecord } from '@/types'
import { formatStatus } from '@/types/attendance'
import { EditUserDialog } from './edit-user-dialog'

const roleBadgeVariant: Record<UserRole, 'default' | 'secondary' | 'outline'> = {
  student: 'default',
  faculty: 'secondary',
  admin: 'outline',
}

const statusBadgeVariant: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  present: 'default',
  late: 'secondary',
  absent: 'destructive',
  excused: 'outline',
  early_leave: 'destructive',
}

const roleBackRoutes: Record<string, { path: string; label: string }> = {
  student: { path: '/students', label: 'Back to Students' },
  faculty: { path: '/faculty', label: 'Back to Faculty' },
  admin: { path: '/admins', label: 'Back to Admins' },
}

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const stateRole = (location.state as { role?: string })?.role
  const setLabel = useBreadcrumbStore((s) => s.setLabel)

  const { data: user, isLoading } = useUser(id!)

  const fullName = user ? `${user.first_name} ${user.last_name}` : null
  usePageTitle(fullName ?? 'User Details')

  useEffect(() => {
    if (fullName) setLabel(fullName)
    return () => setLabel(null)
  }, [fullName, setLabel])
  const { data: attendance = [], isLoading: attendanceLoading } = useUserAttendance(
    id!,
    !!user && user.role === 'student',
  )

  const [editOpen, setEditOpen] = useState(false)
  const [deactivateOpen, setDeactivateOpen] = useState(false)
  const [reactivateOpen, setReactivateOpen] = useState(false)
  const [deregisterOpen, setDeregisterOpen] = useState(false)

  const deactivateMutation = useDeactivateUser()
  const reactivateMutation = useReactivateUser()
  const deregisterMutation = useDeregisterFace()
  const actionLoading = deactivateMutation.isPending || reactivateMutation.isPending || deregisterMutation.isPending

  const handleDeactivate = async () => {
    if (!user) return
    try {
      await deactivateMutation.mutateAsync(user.id)
      toast.success(`${user.first_name} ${user.last_name} has been deactivated.`)
    } catch {
      toast.error('Failed to deactivate user.')
    } finally {
      setDeactivateOpen(false)
    }
  }

  const handleReactivate = async () => {
    if (!user) return
    try {
      await reactivateMutation.mutateAsync(user.id)
      toast.success(`${user.first_name} ${user.last_name} has been reactivated.`)
    } catch {
      toast.error('Failed to reactivate user.')
    } finally {
      setReactivateOpen(false)
    }
  }

  const handleDeregister = async () => {
    if (!user) return
    try {
      await deregisterMutation.mutateAsync(user.id)
      toast.success(`Face data for ${user.first_name} ${user.last_name} has been removed.`)
    } catch {
      toast.error('Failed to deregister face.')
    } finally {
      setDeregisterOpen(false)
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
          {formatStatus(row.original.status)}
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

  const backRoute = roleBackRoutes[user?.role ?? stateRole ?? 'student'] ?? roleBackRoutes.student

  if (!user) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => navigate(backRoute.path)}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          {backRoute.label}
        </Button>
        <p className="text-muted-foreground">User not found.</p>
      </div>
    )
  }

  const initials = `${user.first_name.charAt(0)}${user.last_name.charAt(0)}`.toUpperCase()

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate(backRoute.path)}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        {backRoute.label}
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
              <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </Button>
              {user.is_active ? (
                <>
                  <Button variant="outline" size="sm" disabled={actionLoading} onClick={() => setDeactivateOpen(true)}>
                    <UserX className="mr-2 h-4 w-4" />
                    Deactivate
                  </Button>
                  <AlertDialog open={deactivateOpen} onOpenChange={setDeactivateOpen}>
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
                          onClick={(e) => {
                            e.preventDefault()
                            void handleDeactivate()
                          }}
                          disabled={actionLoading}
                        >
                          {actionLoading ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Deactivating...</>) : 'Deactivate'}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </>
              ) : (
                <>
                  <Button variant="outline" size="sm" disabled={actionLoading} onClick={() => setReactivateOpen(true)}>
                    <UserCheck className="mr-2 h-4 w-4" />
                    Reactivate
                  </Button>
                  <AlertDialog open={reactivateOpen} onOpenChange={setReactivateOpen}>
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
                          onClick={(e) => {
                            e.preventDefault()
                            void handleReactivate()
                          }}
                          disabled={actionLoading}
                        >
                          {actionLoading ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Reactivating...</>) : 'Reactivate'}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </>
              )}

              {user.role === 'student' && (
                <>
                  <Button variant="outline" size="sm" disabled={actionLoading} onClick={() => setDeregisterOpen(true)}>
                    <ScanFace className="mr-2 h-4 w-4" />
                    Deregister Face
                  </Button>
                  <AlertDialog open={deregisterOpen} onOpenChange={setDeregisterOpen}>
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
                          onClick={(e) => {
                            e.preventDefault()
                            void handleDeregister()
                          }}
                          disabled={actionLoading}
                        >
                          {actionLoading ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Removing...</>) : 'Deregister'}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </>
              )}
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

      {user.role === 'student' && (
        <div>
          <h3 className="text-lg font-semibold mb-4">Attendance History</h3>
          <DataTable
            columns={attendanceColumns}
            data={attendance}
            isLoading={attendanceLoading}
            searchColumn="subject_code"
            searchPlaceholder="Search by subject..."
          />
        </div>
      )}

      <EditUserDialog user={user} open={editOpen} onOpenChange={setEditOpen} />
    </div>
  )
}
