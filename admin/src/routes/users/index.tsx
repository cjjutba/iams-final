import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { format } from 'date-fns'
import {
  CheckCircle2,
  MoreHorizontal,
  XCircle,
  Eye,
  UserX,
  UserCheck,
  ScanFace,
} from 'lucide-react'
import { toast } from 'sonner'

import { DataTable } from '@/components/data-tables'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
import { usersService } from '@/services/users.service'
import { faceService } from '@/services/face.service'
import type { UserResponse, UserRole } from '@/types'

const roleBadgeVariant: Record<UserRole, 'default' | 'secondary' | 'outline'> = {
  student: 'default',
  faculty: 'secondary',
  admin: 'outline',
}

function ActionsCell({
  user,
  onRefresh,
}: {
  user: UserResponse
  onRefresh: () => void
}) {
  const navigate = useNavigate()
  const [deactivateOpen, setDeactivateOpen] = useState(false)
  const [reactivateOpen, setReactivateOpen] = useState(false)
  const [deregisterOpen, setDeregisterOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleDeactivate = async () => {
    setLoading(true)
    try {
      await usersService.deactivate(user.id)
      toast.success(`${user.first_name} ${user.last_name} has been deactivated.`)
      onRefresh()
    } catch {
      toast.error('Failed to deactivate user.')
    } finally {
      setLoading(false)
      setDeactivateOpen(false)
    }
  }

  const handleReactivate = async () => {
    setLoading(true)
    try {
      await usersService.reactivate(user.id)
      toast.success(`${user.first_name} ${user.last_name} has been reactivated.`)
      onRefresh()
    } catch {
      toast.error('Failed to reactivate user.')
    } finally {
      setLoading(false)
      setReactivateOpen(false)
    }
  }

  const handleDeregister = async () => {
    setLoading(true)
    try {
      await faceService.deregister(user.id)
      toast.success(`Face data for ${user.first_name} ${user.last_name} has been removed.`)
    } catch {
      toast.error('Failed to deregister face.')
    } finally {
      setLoading(false)
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
            <AlertDialogAction onClick={handleDeactivate} disabled={loading}>
              {loading ? 'Deactivating...' : 'Deactivate'}
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
            <AlertDialogAction onClick={handleReactivate} disabled={loading}>
              {loading ? 'Reactivating...' : 'Reactivate'}
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
            <AlertDialogAction onClick={handleDeregister} disabled={loading}>
              {loading ? 'Removing...' : 'Deregister'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

export default function UsersPage() {
  const [users, setUsers] = useState<UserResponse[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [roleFilter, setRoleFilter] = useState<string>('all')

  const fetchUsers = useCallback(async () => {
    setIsLoading(true)
    try {
      const params = roleFilter !== 'all' ? { role: roleFilter as UserRole } : undefined
      const data = await usersService.list(params)
      setUsers(data)
    } catch {
      toast.error('Failed to load users.')
    } finally {
      setIsLoading(false)
    }
  }, [roleFilter])

  useEffect(() => {
    void fetchUsers()
  }, [fetchUsers])

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
      cell: ({ row }) => (
        <Badge variant={roleBadgeVariant[row.original.role]} className="capitalize">
          {row.original.role}
        </Badge>
      ),
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
      cell: ({ row }) =>
        row.original.is_active ? (
          <Badge variant="default">Active</Badge>
        ) : (
          <Badge variant="destructive">Inactive</Badge>
        ),
    },
    {
      accessorKey: 'email_verified',
      header: 'Email Verified',
      cell: ({ row }) =>
        row.original.email_verified ? (
          <CheckCircle2 className="h-4 w-4 text-green-600" />
        ) : (
          <XCircle className="h-4 w-4 text-red-500" />
        ),
    },
    {
      accessorKey: 'created_at',
      header: 'Created',
      cell: ({ row }) => (
        <span className="text-sm">
          {format(new Date(row.original.created_at), 'MMM d, yyyy')}
        </span>
      ),
    },
    {
      id: 'actions',
      header: '',
      enableSorting: false,
      cell: ({ row }) => (
        <ActionsCell user={row.original} onRefresh={fetchUsers} />
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">User Management</h1>
          <p className="text-muted-foreground mt-1">
            {isLoading ? 'Loading users...' : `${users.length} user${users.length !== 1 ? 's' : ''} total`}
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
        data={users}
        isLoading={isLoading}
        searchColumn="email"
        searchPlaceholder="Search users..."
      />
    </div>
  )
}
