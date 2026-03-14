import { useMemo, useState, useTransition } from 'react'
import { useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { usePageTitle } from '@/hooks/use-page-title'

import { DataTable } from '@/components/data-tables'
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
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useUsers, useDeregisterFace } from '@/hooks/use-queries'
import type { UserResponse } from '@/types'

type StatusFilter = 'all' | 'active' | 'inactive'

function DeregisterAction({ user }: { user: UserResponse }) {
  const [open, setOpen] = useState(false)
  const deregisterMutation = useDeregisterFace()

  const handleDeregister = async () => {
    try {
      await deregisterMutation.mutateAsync(user.id)
      toast.success(`Face deregistered for ${user.first_name} ${user.last_name}`)
    } catch {
      toast.error('Failed to deregister face')
    } finally {
      setOpen(false)
    }
  }

  return (
    <>
      <Button variant="outline" size="sm" disabled={deregisterMutation.isPending} onClick={() => setOpen(true)}>
        {deregisterMutation.isPending ? (
          <><Loader2 className="mr-1 h-3 w-3 animate-spin" />Removing...</>
        ) : (
          <><Trash2 className="mr-1 h-3 w-3" />Deregister</>
        )}
      </Button>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deregister Face</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove the face registration for {user.first_name} {user.last_name}? They will need to re-register their face to use the system.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deregisterMutation.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                void handleDeregister()
              }}
              disabled={deregisterMutation.isPending}
            >
              {deregisterMutation.isPending ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Removing...</>) : 'Deregister'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

const columns: ColumnDef<UserResponse>[] = [
  {
    accessorKey: 'first_name',
    header: 'Student Name',
    cell: ({ row }) => (
      <div>
        <div className="font-medium">{row.original.first_name} {row.original.last_name}</div>
        {row.original.email && (
          <div className="text-sm text-muted-foreground">{row.original.email}</div>
        )}
      </div>
    ),
  },
  {
    accessorKey: 'student_id',
    header: 'Student ID',
    cell: ({ row }) => (
      <span className="text-sm font-mono">{row.original.student_id ?? '\u2014'}</span>
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
    id: 'actions',
    header: '',
    enableSorting: false,
    cell: ({ row }) => (
      <DeregisterAction user={row.original} />
    ),
  },
]

export default function FaceRegistrationsPage() {
  usePageTitle('Face Registrations')
  const navigate = useNavigate()
  const { data: students = [], isLoading } = useUsers({ role: 'student' })

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [isPending, startTransition] = useTransition()

  const filtered = useMemo(() => {
    let result = students
    if (statusFilter === 'active') result = result.filter((s) => s.is_active)
    else if (statusFilter === 'inactive') result = result.filter((s) => !s.is_active)
    return result
  }, [students, statusFilter])

  const hasFilters = statusFilter !== 'all'

  function handleFilterChange<T>(setter: (v: T) => void) {
    return (value: T) => {
      startTransition(() => setter(value))
    }
  }

  function clearFilters() {
    startTransition(() => {
      setStatusFilter('all')
    })
  }

  const showSkeleton = isLoading || isPending

  const filterToolbar = (
    <>
      <Select value={statusFilter} onValueChange={handleFilterChange(setStatusFilter)}>
        <SelectTrigger className="w-[130px] h-9">
          <SelectValue placeholder="Status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Status</SelectItem>
          <SelectItem value="active">Active</SelectItem>
          <SelectItem value="inactive">Inactive</SelectItem>
        </SelectContent>
      </Select>

      {hasFilters && (
        <Button variant="ghost" size="sm" onClick={clearFilters} className="h-9 px-2 text-muted-foreground">
          Clear
        </Button>
      )}
    </>
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Face Registrations</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isLoading
              ? 'Loading...'
              : hasFilters
                ? `${filtered.length} of ${students.length} registrations`
                : `${students.length} face registration${students.length !== 1 ? 's' : ''}`}
          </p>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        isLoading={showSkeleton}
        searchPlaceholder="Search students..."
        searchColumn="first_name"
        toolbar={filterToolbar}
        onRowClick={(row) => navigate(`/users/${row.id}`, { state: { role: 'student' } })}
      />
    </div>
  )
}
