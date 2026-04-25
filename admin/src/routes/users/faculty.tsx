import { useMemo, useState, useTransition } from 'react'
import { useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { safeFormat } from '@/lib/utils'
import { CheckCircle2, XCircle, Plus } from 'lucide-react'
import { usePageTitle } from '@/hooks/use-page-title'

import { DataTable } from '@/components/data-tables'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useUsers } from '@/hooks/use-queries'
import type { UserResponse } from '@/types'
import { CreateUserDialog } from './create-user-dialog'
import { UserActionsCell } from './user-actions'
import { tokenMatches, joinHaystack, isoDateHaystackParts } from '@/lib/search'

function buildFacultyHaystack(u: UserResponse): string {
  return joinHaystack([
    u.first_name,
    u.last_name,
    `${u.first_name} ${u.last_name}`,
    u.email,
    u.phone,
    u.is_active ? 'Active' : 'Inactive',
    u.email_verified ? 'Verified' : 'Not Verified',
    ...isoDateHaystackParts(u.created_at),
  ])
}

type StatusFilter = 'all' | 'active' | 'inactive'
type EmailFilter = 'all' | 'verified' | 'not_verified'

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
    accessorKey: 'phone',
    header: 'Phone',
    cell: ({ row }) => (
      <span className="text-sm">{row.original.phone ?? '\u2014'}</span>
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
    header: 'Email',
    cell: ({ row }) =>
      row.original.email_verified ? (
        <span className="inline-flex items-center gap-1.5 text-sm text-green-600">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Verified
        </span>
      ) : (
        <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
          <XCircle className="h-3.5 w-3.5" />
          Not Verified
        </span>
      ),
  },
  {
    accessorKey: 'created_at',
    header: 'Added',
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
    cell: ({ row }) => <UserActionsCell user={row.original} />,
  },
]

export default function FacultyPage() {
  usePageTitle('Faculty')
  const navigate = useNavigate()
  const { data: faculty = [], isLoading } = useUsers({ role: 'faculty' })
  const [dialogOpen, setDialogOpen] = useState(false)

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [emailFilter, setEmailFilter] = useState<EmailFilter>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [isPending, startTransition] = useTransition()

  const filtered = useMemo(() => {
    let result = faculty
    if (statusFilter === 'active') result = result.filter((f) => f.is_active)
    else if (statusFilter === 'inactive') result = result.filter((f) => !f.is_active)

    if (emailFilter === 'verified') result = result.filter((f) => f.email_verified)
    else if (emailFilter === 'not_verified') result = result.filter((f) => !f.email_verified)

    if (searchQuery.trim()) {
      result = result.filter((f) => tokenMatches(buildFacultyHaystack(f), searchQuery))
    }

    return result
  }, [faculty, statusFilter, emailFilter, searchQuery])

  const hasFilters =
    statusFilter !== 'all' || emailFilter !== 'all' || searchQuery.trim().length > 0

  function handleFilterChange<T>(setter: (v: T) => void) {
    return (value: string) => {
      startTransition(() => setter(value as T))
    }
  }

  function clearFilters() {
    startTransition(() => {
      setStatusFilter('all')
      setEmailFilter('all')
      setSearchQuery('')
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

      <Select value={emailFilter} onValueChange={handleFilterChange(setEmailFilter)}>
        <SelectTrigger className="w-[140px] h-9">
          <SelectValue placeholder="Email" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Email</SelectItem>
          <SelectItem value="verified">Verified</SelectItem>
          <SelectItem value="not_verified">Not Verified</SelectItem>
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
          <h1 className="text-2xl font-semibold tracking-tight">Faculty</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isLoading
              ? 'Loading...'
              : hasFilters
                ? `${filtered.length} of ${faculty.length} faculty members`
                : `${faculty.length} faculty member${faculty.length !== 1 ? 's' : ''}`}
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Faculty
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        isLoading={showSkeleton}
        searchPlaceholder="Search by name, email, phone, status..."
        globalFilter={searchQuery}
        onGlobalFilterChange={(v) => startTransition(() => setSearchQuery(v))}
        globalFilterFn={() => true}
        toolbar={filterToolbar}
        onRowClick={(row) => navigate(`/users/${row.id}`, { state: { role: 'faculty' } })}
      />

      <CreateUserDialog role="faculty" open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  )
}
