import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'

import { DataTable } from '@/components/data-tables'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { analyticsService } from '@/services/analytics.service'
import type { AtRiskStudent } from '@/types'

const riskColors: Record<string, string> = {
  HIGH: 'bg-red-100 text-red-800 hover:bg-red-100',
  MEDIUM: 'bg-yellow-100 text-yellow-800 hover:bg-yellow-100',
  LOW: 'bg-green-100 text-green-800 hover:bg-green-100',
}

const columns: ColumnDef<AtRiskStudent>[] = [
  {
    accessorKey: 'student_name',
    header: 'Student',
  },
  {
    accessorKey: 'attendance_rate',
    header: 'Attendance Rate',
    cell: ({ row }) => {
      const rate = row.original.attendance_rate
      const color = rate < 70 ? 'text-red-600' : rate < 85 ? 'text-yellow-600' : 'text-green-600'
      return <span className={`font-medium ${color}`}>{rate.toFixed(1)}%</span>
    },
  },
  {
    accessorKey: 'risk_level',
    header: 'Risk Level',
    cell: ({ row }) => (
      <Badge className={riskColors[row.original.risk_level]}>
        {row.original.risk_level}
      </Badge>
    ),
  },
  {
    accessorKey: 'missed_classes',
    header: 'Missed Classes',
  },
]

export default function AtRiskPage() {
  const [students, setStudents] = useState<AtRiskStudent[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    try {
      const data = await analyticsService.atRisk()
      setStudents(data)
    } catch {
      toast.error('Failed to load at-risk students')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchData()
  }, [fetchData])

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/analytics">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">At-Risk Students</h1>
          <p className="text-muted-foreground">Students with low attendance rates requiring attention</p>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={students}
        isLoading={loading}
        searchPlaceholder="Search students..."
        searchColumn="student_name"
      />
    </div>
  )
}
