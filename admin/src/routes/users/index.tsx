import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePageTitle } from '@/hooks/use-page-title'
import { type ColumnDef } from '@tanstack/react-table'
import { safeFormat } from '@/lib/utils'
import {
  Loader2,
  MoreHorizontal,
  Eye,
  UserX,
  UserCheck,
  ScanFace,
} from 'lucide-react'
import { toast } from 'sonner'

import { DataTable } from '@/components/data-tables'
import { Button } from '@/components/ui/button'
import {
  ActiveStatusPill,
  EmailVerifiedPill,
  UserRolePill,
} from '@/components/shared/status-pills'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  useUsers,
  useDeactivateUser,
  useReactivateUser,
  useDeregisterFace,
} from '@/hooks/use-queries'
import type { UserResponse, UserRole } from '@/types'
import { tokenMatches, joinHaystack, isoDateHaystackParts } from '@/lib/search'

function buildUserHaystack(u: UserResponse): string {
  return joinHaystack([
    u.first_name,
    u.last_name,
    `${u.first_name} ${u.last_name}`,
    u.email,
    u.phone,
    u.role,
    u.student_id,
    u.is_active ? 'Active' : 'Inactive',
    u.email_verified ? 'Verified' : 'Unverified',
    ...isoDateHaystackParts(u.created_at),
  ])
}

function ActionsCell({ user }: { user: UserResponse }) {
  const navigate = useNavigate()
  const [deactivateOpen, setDeactivateOpen] = useState(false)
  const [reactivateOpen, setReactivateOpen] = useState(false)
  const [deregisterOpen, setDeregisterOpen] = useState(false)

  const deactivateMutation = useDeactivateUser()
  const reactivateMutation = useReactivateUser()
  const deregisterMutation = useDeregisterFace()
  const loading = deactivateMutation.isPending || reactivateMutation.isPending || deregisterMutation.isPending

  const handleDeactivate = async () => {
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
    try {
      await deregisterMutation.mutateAsync(user.id)
      toast.success(`Face data for ${user.first_name} ${user.last_name} has been removed.`)
    } catch {
      toast.error('Failed to deregister face.')
    } finally {
      setDeregisterOpen(false)
    }
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
            <MoreHorizontal className="h-4 w-4" />
            <span className="sr-only">Open menu</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => navigate(`/users/${user.id}`)}>
            <Eye className="mr-2 h-4 w-4" />
            View Details
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          {user.is_active ? (
            <DropdownMenuItem onClick={() => setDeactivateOpen(true)}>
              <UserX className="mr-2 h-4 w-4" />
              Deactivate
            </DropdownMenuItem>
          ) : (
            <DropdownMenuItem onClick={() => setReactivateOpen(true)}>
              <UserCheck className="mr-2 h-4 w-4" />
              Reactivate
            </DropdownMenuItem>
          )}
          <DropdownMenuItem onClick={() => setDeregisterOpen(true)}>
            <ScanFace className="mr-2 h-4 w-4" />
            Deregister Face
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={deactivateOpen} onOpenChange={setDeactivateOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate User</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to deactivate {user.first_name} {user.last_name}?
              They will no longer be able to access the system.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={loading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                void handleDeactivate()
              }}
              disabled={loading}
            >
              {loading ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Deactivating...</>) : 'Deactivate'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={reactivateOpen} onOpenChange={setReactivateOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reactivate User</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to reactivate {user.first_name} {user.last_name}?
              They will regain access to the system.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={loading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                void handleReactivate()
              }}
              disabled={loading}
            >
              {loading ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Reactivating...</>) : 'Reactivate'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={deregisterOpen} onOpenChange={setDeregisterOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deregister Face</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove face registration data for{' '}
              {user.first_name} {user.last_name}? They will need to re-register
              their face to use the attendance system.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={loading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                void handleDeregister()
              }}
              disabled={loading}
            >
              {loading ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Removing...</>) : 'Deregister'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

export default function UsersPage() {
  usePageTitle('Users')
  const navigate = useNavigate()
  const [roleFilter, setRoleFilter] = useState<string>('all')

  const queryParams = useMemo(
    () => (roleFilter !== 'all' ? { role: roleFilter as UserRole } : undefined),
    [roleFilter],
  )
  const { data: users = [], isLoading } = useUsers(queryParams)

  const [searchQuery, setSearchQuery] = useState('')

  const filteredUsers = useMemo(() => {
    if (!searchQuery.trim()) return users
    return users.filter((u) => tokenMatches(buildUserHaystack(u), searchQuery))
  }, [users, searchQuery])

  const columns: ColumnDef<UserResponse>[] = [
    {
      accessorKey: 'first_name',
      header: 'Name',
      cell: ({ row }) => (
        <div>
          <div className="font-medium">
            {row.original.first_name} {row.original.last_name}
          </div>
          <div className="text-sm text-muted-foreground">{row.original.email}</div>
        </div>
      ),
    },
    {
      accessorKey: 'role',
      header: 'Role',
      cell: ({ row }) => <UserRolePill role={row.original.role} />,
    },
    {
      accessorKey: 'student_id',
      header: 'Student ID',
      cell: ({ row }) => (
        <span className="text-sm">
          {row.original.student_id ?? '\u2014'}
        </span>
      ),
    },
    {
      accessorKey: 'is_active',
      header: 'Status',
      cell: ({ row }) => <ActiveStatusPill active={row.original.is_active} />,
    },
    {
      accessorKey: 'email_verified',
      header: 'Email',
      cell: ({ row }) => <EmailVerifiedPill verified={row.original.email_verified} />,
    },
    {
      accessorKey: 'created_at',
      header: 'Created',
      cell: ({ row }) => (
        <span className="text-sm">
          {safeFormat(row.original.created_at, 'MMM d, yyyy')}
        </span>
      ),
    },
    {
      id: 'actions',
      header: '',
      enableSorting: false,
      cell: ({ row }) => (
        <ActionsCell user={row.original} />
      ),
    },
  ]

  if (isLoading) {
    // Mirror the loaded layout (header + role filter + toolbar + table +
    // pagination) so the cut-over to real data doesn't shift the page.
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-7 w-44" />
            <Skeleton className="h-4 w-36" />
          </div>
          <Skeleton className="h-9 w-[150px] rounded-md" />
        </div>

        <div>
          <div className="flex items-center justify-between gap-4 py-4">
            <Skeleton className="h-9 w-full max-w-sm rounded-md" />
          </div>

          <div className="rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Student ID</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-[60px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from({ length: 10 }).map((_, i) => (
                  <TableRow key={`users-skel-${String(i)}`}>
                    <TableCell>
                      <div className="space-y-1.5">
                        <Skeleton className="h-4 w-40" />
                        <Skeleton className="h-3 w-52" />
                      </div>
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-16 rounded-full" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-20" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-16 rounded-full" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-20 rounded-full" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-3 w-24" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="ml-auto h-8 w-8 rounded-md" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="flex items-center justify-between px-2 py-4">
            <Skeleton className="h-4 w-44" />
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-8 w-[70px] rounded-md" />
              </div>
              <div className="flex items-center gap-1">
                <Skeleton className="h-8 w-8 rounded-md" />
                <Skeleton className="h-8 w-8 rounded-md" />
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">User Management</h1>
          <p className="text-muted-foreground mt-1">
            {searchQuery.trim()
              ? `${filteredUsers.length} of ${users.length} users`
              : `${users.length} user${users.length !== 1 ? 's' : ''} total`}
          </p>
        </div>
        <Select value={roleFilter} onValueChange={setRoleFilter}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Filter by role" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Roles</SelectItem>
            <SelectItem value="student">Student</SelectItem>
            <SelectItem value="faculty">Faculty</SelectItem>
            <SelectItem value="admin">Admin</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <DataTable
        columns={columns}
        data={filteredUsers}
        isLoading={isLoading}
        searchPlaceholder="Search by name, email, role, ID, status..."
        globalFilter={searchQuery}
        onGlobalFilterChange={setSearchQuery}
        globalFilterFn={() => true}
        onRowClick={(row) => navigate(`/users/${row.id}`, { state: { role: row.role } })}
      />
    </div>
  )
}
