import { useMemo, useState, useTransition } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { ArrowLeft } from 'lucide-react'
import { usePageTitle } from '@/hooks/use-page-title'

import { DataTable } from '@/components/data-tables'
import { Button } from '@/components/ui/button'
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
  const [, startSearchTransition] = useTransition()
  const filteredStudents = useMemo(() => {
    if (!searchQuery.trim()) return students
    return students.filter((s) => tokenMatches(buildAtRiskHaystack(s), searchQuery))
  }, [students, searchQuery])

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
        onGlobalFilterChange={(v) => startSearchTransition(() => setSearchQuery(v))}
        globalFilterFn={() => true}
        onRowClick={(row) => navigate(`/users/${row.student_id}`, { state: { role: 'student' } })}
      />
    </div>
  )
}
