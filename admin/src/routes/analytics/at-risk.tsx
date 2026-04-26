import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { ArrowLeft } from 'lucide-react'
import { usePageTitle } from '@/hooks/use-page-title'

import { DataTable } from '@/components/data-tables'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useAtRiskStudents } from '@/hooks/use-queries'
import type { AtRiskStudent } from '@/types'
import { formatStatus } from '@/types/attendance'
import { tokenMatches, joinHaystack } from '@/lib/search'
import {
  AttendanceRatePill,
  RiskLevelPill,
} from '@/components/shared/status-pills'

function buildAtRiskHaystack(s: AtRiskStudent): string {
  return joinHaystack([
    s.student_name,
    s.student_id,
    formatStatus(s.risk_level),
    s.risk_level,
    `${s.attendance_rate.toFixed(1)}%`,
    `${s.missed_classes} missed`,
  ])
}

const columns: ColumnDef<AtRiskStudent>[] = [
  {
    accessorKey: 'student_name',
    header: 'Student',
    cell: ({ row }) => (
      <span className="font-medium">{row.original.student_name}</span>
    ),
  },
  {
    accessorKey: 'attendance_rate',
    header: 'Attendance Rate',
    cell: ({ row }) => <AttendanceRatePill rate={row.original.attendance_rate} />,
  },
  {
    accessorKey: 'risk_level',
    header: 'Risk Level',
    cell: ({ row }) => <RiskLevelPill level={row.original.risk_level} />,
  },
  {
    accessorKey: 'missed_classes',
    header: 'Missed Classes',
    cell: ({ row }) => (
      <span className="text-sm tabular-nums">{row.original.missed_classes}</span>
    ),
  },
]

export default function AtRiskPage() {
  usePageTitle('At-Risk Students')
  const navigate = useNavigate()
  const { data: students = [], isLoading } = useAtRiskStudents()

  const [searchQuery, setSearchQuery] = useState('')
  const filteredStudents = useMemo(() => {
    if (!searchQuery.trim()) return students
    return students.filter((s) => tokenMatches(buildAtRiskHaystack(s), searchQuery))
  }, [students, searchQuery])

  if (isLoading) {
    // Mirror the loaded layout (header + toolbar + table + pagination) so
    // the cut-over to real data doesn't shift the page.
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Skeleton className="h-9 w-9 rounded-md" />
          <div className="space-y-2">
            <Skeleton className="h-7 w-44" />
            <Skeleton className="h-4 w-72" />
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between gap-4 py-4">
            <Skeleton className="h-9 w-full max-w-sm rounded-md" />
          </div>

          <div className="rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Student</TableHead>
                  <TableHead>Attendance Rate</TableHead>
                  <TableHead>Risk Level</TableHead>
                  <TableHead>Missed Classes</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from({ length: 10 }).map((_, i) => (
                  <TableRow key={`atrisk-skel-${String(i)}`}>
                    <TableCell>
                      <Skeleton className="h-4 w-40" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-16 rounded-full" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-5 w-20 rounded-full" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-8" />
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
      <div className="flex items-center gap-3">
        <Link to="/analytics">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">At-Risk Students</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Students with low attendance rates requiring attention
          </p>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={filteredStudents}
        isLoading={isLoading}
        searchPlaceholder="Search by name, risk level, attendance rate..."
        globalFilter={searchQuery}
        onGlobalFilterChange={setSearchQuery}
        globalFilterFn={() => true}
        onRowClick={(row) => navigate(`/users/${row.student_id}`, { state: { role: 'student' } })}
      />
    </div>
  )
}
