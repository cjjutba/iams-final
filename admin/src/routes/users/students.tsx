import { useMemo, useState, useTransition } from 'react'
import { useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { safeFormat } from '@/lib/utils'
import { CheckCircle2, XCircle, Plus, ScanFace } from 'lucide-react'
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
import { useStudentRecords } from '@/hooks/use-queries'
import type { StudentRecordWithStatus } from '@/types'
import { CreateUserDialog } from './create-user-dialog'
import { tokenMatches, joinHaystack, isoDateHaystackParts } from '@/lib/search'

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
    s.is_registered ? 'Registered' : 'Not Registered',
    s.has_face_registered ? 'Face Enrolled' : 'Face Not Enrolled',
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
      <span className="text-sm font-mono">{row.original.student_id}</span>
    ),
  },
  {
    accessorKey: 'course',
    header: 'Course & Year',
    cell: ({ row }) => {
      const { course, year_level, section } = row.original
      if (!course && !year_level) return <span className="text-sm text-muted-foreground">{'\u2014'}</span>
      const parts = [course, year_level ? `Year ${year_level}` : null, section ? `Section ${section}` : null].filter(Boolean)
      return <span className="text-sm">{parts.join(' \u2022 ')}</span>
    },
  },
  {
    accessorKey: 'is_registered',
    header: 'App Status',
    cell: ({ row }) => {
      if (!row.original.is_registered) {
        return (
          <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
            <XCircle className="h-3.5 w-3.5" />
            Not Registered
          </span>
        )
      }
      return (
        <span className="inline-flex items-center gap-1.5 text-sm text-green-600">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Registered
        </span>
      )
    },
  },
  {
    accessorKey: 'has_face_registered',
    header: 'Face',
    cell: ({ row }) => {
      if (!row.original.is_registered) {
        return <span className="text-sm text-muted-foreground">{'\u2014'}</span>
      }
      return row.original.has_face_registered ? (
        <span className="inline-flex items-center gap-1.5 text-sm text-green-600">
          <ScanFace className="h-3.5 w-3.5" />
          Enrolled
        </span>
      ) : (
        <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
          <ScanFace className="h-3.5 w-3.5" />
          Not Enrolled
        </span>
      )
    },
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
    accessorKey: 'created_at',
    header: 'Added',
    cell: ({ row }) => (
      <span className="text-sm">
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
          <SelectValue placeholder="App Status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All App Status</SelectItem>
          <SelectItem value="registered">Registered</SelectItem>
          <SelectItem value="not_registered">Not Registered</SelectItem>
        </SelectContent>
      </Select>

      <Select value={faceFilter} onValueChange={handleFilterChange(setFaceFilter)}>
        <SelectTrigger className="w-[140px] h-9">
          <SelectValue placeholder="Face" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Face</SelectItem>
          <SelectItem value="enrolled">Enrolled</SelectItem>
          <SelectItem value="not_enrolled">Not Enrolled</SelectItem>
        </SelectContent>
      </Select>

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

  const showSkeleton = isLoading || isPending

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Students</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isLoading
              ? 'Loading...'
              : hasFilters
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
        onGlobalFilterChange={(v) => startTransition(() => setSearchQuery(v))}
        globalFilterFn={() => true}
        toolbar={filterToolbar}
        onRowClick={(row) => navigate(`/students/${row.student_id}`)}
      />

      <CreateUserDialog role="student" open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  )
}
