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
import { useStudentRecords } from '@/hooks/use-queries'
import type { StudentRecordWithStatus } from '@/types'
import { CreateUserDialog } from './create-user-dialog'
import { tokenMatches, joinHaystack, isoDateHaystackParts } from '@/lib/search'
import {
  ActiveStatusPill,
  AppLinkedPill,
  FaceStatusPill,
} from '@/components/shared/status-pills'

function buildStudentHaystack(s: StudentRecordWithStatus): string {
  const fullName = [s.first_name, s.middle_name, s.last_name].filter(Boolean).join(' ')
  return joinHaystack([
    s.first_name,
    s.middle_name,
    s.last_name,
    fullName,
    s.email,
    s.student_id,
    s.course,
    s.year_level != null ? `Year ${s.year_level}` : null,
    s.section ? `Section ${s.section}` : null,
    s.is_active ? 'Active' : 'Inactive',
    s.is_registered ? 'App Linked' : 'Not Linked',
    s.has_face_registered ? 'Face Enrolled' : 'Face Pending',
    ...isoDateHaystackParts(s.created_at),
  ])
}

type AppFilter = 'all' | 'registered' | 'not_registered'
type FaceFilter = 'all' | 'enrolled' | 'not_enrolled'
type StatusFilter = 'all' | 'active' | 'inactive'

const columns: ColumnDef<StudentRecordWithStatus>[] = [
  {
    accessorKey: 'first_name',
    header: 'Name',
    cell: ({ row }) => (
      <div>
        <div className="font-medium">
          {row.original.first_name}{' '}
          {row.original.middle_name ? `${row.original.middle_name} ` : ''}
          {row.original.last_name}
        </div>
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
      <span className="font-mono text-xs text-muted-foreground">{row.original.student_id}</span>
    ),
  },
  {
    accessorKey: 'course',
    header: 'Course & Year',
    cell: ({ row }) => {
      const { course, year_level, section } = row.original
      if (!course && !year_level)
        return <span className="text-sm text-muted-foreground">—</span>
      const parts = [
        course,
        year_level ? `Year ${year_level}` : null,
        section ? `Section ${section}` : null,
      ].filter(Boolean)
      return <span className="text-sm">{parts.join(' · ')}</span>
    },
  },
  {
    accessorKey: 'is_registered',
    header: 'App',
    cell: ({ row }) => <AppLinkedPill linked={row.original.is_registered} />,
  },
  {
    accessorKey: 'has_face_registered',
    header: 'Face',
    cell: ({ row }) => (
      <FaceStatusPill
        registered={row.original.has_face_registered}
        applicable={row.original.is_registered}
      />
    ),
  },
  {
    accessorKey: 'is_active',
    header: 'Status',
    cell: ({ row }) => <ActiveStatusPill active={row.original.is_active} />,
  },
  {
    accessorKey: 'created_at',
    header: 'Added',
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {safeFormat(row.original.created_at, 'MMM d, yyyy')}
      </span>
    ),
  },
]

export default function StudentsPage() {
  usePageTitle('Students')
  const navigate = useNavigate()
  const { data: students = [], isLoading } = useStudentRecords()
  const [dialogOpen, setDialogOpen] = useState(false)

  const [appFilter, setAppFilter] = useState<AppFilter>('all')
  const [faceFilter, setFaceFilter] = useState<FaceFilter>('all')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [isPending, startTransition] = useTransition()

  const filtered = useMemo(() => {
    let result = students
    if (appFilter === 'registered') result = result.filter((s) => s.is_registered)
    else if (appFilter === 'not_registered') result = result.filter((s) => !s.is_registered)

    if (faceFilter === 'enrolled') result = result.filter((s) => s.has_face_registered)
    else if (faceFilter === 'not_enrolled') result = result.filter((s) => s.is_registered && !s.has_face_registered)

    if (statusFilter === 'active') result = result.filter((s) => s.is_active)
    else if (statusFilter === 'inactive') result = result.filter((s) => !s.is_active)

    if (searchQuery.trim()) {
      result = result.filter((s) => tokenMatches(buildStudentHaystack(s), searchQuery))
    }

    // Default sort: surface students who have actually completed app
    // onboarding so the registry doesn't open on a wall of "PENDING-XXXX"
    // admin-added rows. Tiers, top -> bottom:
    //   3. App-registered AND face enrolled (fully onboarded — the rows
    //      that actually participate in attendance)
    //   2. App-registered, no face yet (joined the app, registration step
    //      pending)
    //   1. Not app-registered, somehow has a face row (data anomaly,
    //      sorted above no-app entries so it surfaces)
    //   0. Admin-added only, no app account
    // Within each tier, newest-first by created_at so recent additions
    // remain visible at the top of their group. Clicking a column header
    // overrides this — TanStack's sorting state takes precedence once set.
    const tier = (s: StudentRecordWithStatus) =>
      (s.is_registered ? 2 : 0) + (s.has_face_registered ? 1 : 0)
    result = [...result].sort((a, b) => {
      const ds = tier(b) - tier(a)
      if (ds !== 0) return ds
      const at = a.created_at ?? ''
      const bt = b.created_at ?? ''
      return bt.localeCompare(at)
    })

    return result
  }, [students, appFilter, faceFilter, statusFilter, searchQuery])

  const hasFilters =
    appFilter !== 'all' ||
    faceFilter !== 'all' ||
    statusFilter !== 'all' ||
    searchQuery.trim().length > 0

  function handleFilterChange<T>(setter: (v: T) => void) {
    return (value: string) => {
      startTransition(() => setter(value as T))
    }
  }

  function clearFilters() {
    startTransition(() => {
      setAppFilter('all')
      setFaceFilter('all')
      setStatusFilter('all')
      setSearchQuery('')
    })
  }

  const filterToolbar = (
    <>
      <Select value={appFilter} onValueChange={handleFilterChange(setAppFilter)}>
        <SelectTrigger className="w-[150px] h-9">
          <SelectValue placeholder="App" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All app states</SelectItem>
          <SelectItem value="registered">App linked</SelectItem>
          <SelectItem value="not_registered">Not linked</SelectItem>
        </SelectContent>
      </Select>

      <Select value={faceFilter} onValueChange={handleFilterChange(setFaceFilter)}>
        <SelectTrigger className="w-[140px] h-9">
          <SelectValue placeholder="Face" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All face states</SelectItem>
          <SelectItem value="enrolled">Face enrolled</SelectItem>
          <SelectItem value="not_enrolled">Face pending</SelectItem>
        </SelectContent>
      </Select>

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

      {hasFilters && (
        <Button variant="ghost" size="sm" onClick={clearFilters} className="h-9 px-2 text-muted-foreground">
          Clear
        </Button>
      )}
    </>
  )

  const showSkeleton = isLoading || isPending

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
            <Skeleton className="h-7 w-32" />
            <Skeleton className="h-4 w-44" />
          </div>
          <Skeleton className="h-9 w-32 rounded-md" />
        </div>

        <div>
          {/* Toolbar — search + 3 selects + (optional) Clear */}
          <div className="flex items-center justify-between gap-4 py-4">
            <Skeleton className="h-9 w-full max-w-sm rounded-md" />
            <div className="flex items-center gap-2">
              <Skeleton className="h-9 w-[150px] rounded-md" />
              <Skeleton className="h-9 w-[140px] rounded-md" />
              <Skeleton className="h-9 w-[130px] rounded-md" />
            </div>
          </div>

          {/* Table — render real header so column proportions auto-size
              the same as the loaded table. */}
          <div className="rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Student ID</TableHead>
                  <TableHead>Course &amp; Year</TableHead>
                  <TableHead>App</TableHead>
                  <TableHead>Face</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Added</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from({ length: 10 }).map((_, i) => (
                  <TableRow key={`students-skel-${String(i)}`}>
                    <TableCell>
                      <div className="space-y-1.5">
                        <Skeleton className="h-4 w-40" />
                        <Skeleton className="h-3 w-52" />
                      </div>
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-3 w-20" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-44" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-20 rounded-full" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-20 rounded-full" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-16 rounded-full" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-3 w-24" />
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
          <h1 className="text-2xl font-semibold tracking-tight">Students</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {hasFilters
              ? `${filtered.length} of ${students.length} students`
              : `${students.length} student${students.length !== 1 ? 's' : ''} in registry`}
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Student
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        isLoading={showSkeleton}
        searchPlaceholder="Search by name, ID, course, year, status..."
        globalFilter={searchQuery}
        onGlobalFilterChange={setSearchQuery}
        globalFilterFn={() => true}
        toolbar={filterToolbar}
        onRowClick={(row) => navigate(`/students/${row.student_id}`)}
      />

      <CreateUserDialog role="student" open={dialogOpen} onOpenChange={setDialogOpen}/>
    </div>
  )
}
