import { useMemo, useState, useTransition } from 'react'
import { useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { safeFormat } from '@/lib/utils'
import { Plus } from 'lucide-react'
import { usePageTitle } from '@/hooks/use-page-title'

import { DataTable } from '@/components/data-tables'
import { Button } from '@/components/ui/button'
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
import { useUsers } from '@/hooks/use-queries'
import type { UserResponse } from '@/types'
import { CreateUserDialog } from './create-user-dialog'
import { UserActionsCell } from './user-actions'
import { tokenMatches, joinHaystack, isoDateHaystackParts } from '@/lib/search'
import {
  ActiveStatusPill,
  EmailVerifiedPill,
} from '@/components/shared/status-pills'

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
      <span className="text-sm text-muted-foreground">
        {row.original.phone ?? '—'}
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
    header: 'Joined',
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
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
          <SelectItem value="all">All status</SelectItem>
          <SelectItem value="active">Active</SelectItem>
          <SelectItem value="inactive">Inactive</SelectItem>
        </SelectContent>
      </Select>

      <Select value={emailFilter} onValueChange={handleFilterChange(setEmailFilter)}>
        <SelectTrigger className="w-[140px] h-9">
          <SelectValue placeholder="Email" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All email</SelectItem>
          <SelectItem value="verified">Verified</SelectItem>
          <SelectItem value="not_verified">Not verified</SelectItem>
        </SelectContent>
      </Select>

      {hasFilters && (
        <Button variant="ghost" size="sm" onClick={clearFilters} className="h-9 px-2 text-muted-foreground">
          Clear
        </Button>
      )}
    </>
  )

  if (isLoading) {
    // Mirror the loaded layout (header + toolbar + table + pagination) so
    // the cut-over to real data doesn't shift the page. Used only on
    // initial fetch — `isPending` (filter transitions) keeps the toolbar
    // interactive and uses the DataTable's own row-level skeleton.
    return (
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-7 w-28" />
            <Skeleton className="h-4 w-44" />
          </div>
          <Skeleton className="h-9 w-32 rounded-md" />
        </div>

        <div>
          {/* Toolbar — search + 2 selects */}
          <div className="flex items-center justify-between gap-4 py-4">
            <Skeleton className="h-9 w-full max-w-sm rounded-md" />
            <div className="flex items-center gap-2">
              <Skeleton className="h-9 w-[130px] rounded-md" />
              <Skeleton className="h-9 w-[140px] rounded-md" />
            </div>
          </div>

          {/* Table — render real header so column proportions auto-size
              the same as the loaded table. */}
          <div className="rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Joined</TableHead>
                  <TableHead className="w-[60px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from({ length: 10 }).map((_, i) => (
                  <TableRow key={`faculty-skel-${String(i)}`}>
                    <TableCell>
                      <div className="space-y-1.5">
                        <Skeleton className="h-4 w-40" />
                        <Skeleton className="h-3 w-52" />
                      </div>
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-28" />
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

          {/* Pagination */}
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
          <h1 className="text-2xl font-semibold tracking-tight">Faculty</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {hasFilters
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
        onGlobalFilterChange={setSearchQuery}
        globalFilterFn={() => true}
        toolbar={filterToolbar}
        onRowClick={(row) => navigate(`/users/${row.id}`, { state: { role: 'faculty' } })}
      />

      <CreateUserDialog role="faculty" open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  )
}
