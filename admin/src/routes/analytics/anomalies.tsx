import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { format } from 'date-fns'
import { ArrowLeft, CheckCircle } from 'lucide-react'
import { toast } from 'sonner'

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
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { analyticsService } from '@/services/analytics.service'
import type { AttendanceAnomaly } from '@/types'

function AnomalyActions({ anomaly, onResolved }: { anomaly: AttendanceAnomaly; onResolved: () => void }) {
  const [resolving, setResolving] = useState(false)

  if (anomaly.resolved) {
    return <Badge className="bg-green-100 text-green-800 hover:bg-green-100">Resolved</Badge>
  }

  const handleResolve = async () => {
    setResolving(true)
    try {
      await analyticsService.resolveAnomaly(anomaly.id)
      toast.success('Anomaly marked as resolved')
      onResolved()
    } catch {
      toast.error('Failed to resolve anomaly')
    } finally {
      setResolving(false)
    }
  }

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="outline" size="sm" disabled={resolving}>
          <CheckCircle className="mr-1 h-3 w-3" />
          Resolve
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Resolve Anomaly</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to mark this anomaly as resolved? This action indicates the issue has been reviewed.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={() => void handleResolve()}>Resolve</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

const anomalyTypeLabels: Record<string, string> = {
  FREQUENT_ABSENTEE: 'Frequent Absentee',
  CHRONIC_ABSENTEE: 'Chronic Absentee',
  PATTERN_CHANGE: 'Pattern Change',
}

export default function AnomaliesPage() {
  const [anomalies, setAnomalies] = useState<AttendanceAnomaly[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    try {
      const data = await analyticsService.anomalies()
      setAnomalies(data)
    } catch {
      toast.error('Failed to load anomalies')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchData()
  }, [fetchData])

  const columns: ColumnDef<AttendanceAnomaly>[] = [
    {
      accessorKey: 'student_id',
      header: 'Student ID',
    },
    {
      accessorKey: 'anomaly_type',
      header: 'Type',
      cell: ({ row }) => (
        <Badge variant="outline">
          {anomalyTypeLabels[row.original.anomaly_type] ?? row.original.anomaly_type}
        </Badge>
      ),
    },
    {
      accessorKey: 'severity',
      header: 'Severity',
    },
    {
      accessorKey: 'description',
      header: 'Description',
      cell: ({ row }) => {
        const desc = row.original.description
        return (
          <span className="max-w-[300px] truncate block" title={desc}>
            {desc}
          </span>
        )
      },
    },
    {
      accessorKey: 'detected_at',
      header: 'Detected',
      cell: ({ row }) => {
        try {
          return format(new Date(row.original.detected_at), 'MMM d, yyyy')
        } catch {
          return row.original.detected_at
        }
      },
    },
    {
      accessorKey: 'resolved',
      header: 'Status',
      cell: ({ row }) => (
        <Badge className={row.original.resolved
          ? 'bg-green-100 text-green-800 hover:bg-green-100'
          : 'bg-red-100 text-red-800 hover:bg-red-100'
        }>
          {row.original.resolved ? 'Resolved' : 'Unresolved'}
        </Badge>
      ),
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => (
        <AnomalyActions anomaly={row.original} onResolved={() => void fetchData()} />
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/analytics">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Anomaly Detection</h1>
          <p className="text-muted-foreground">Review and resolve attendance anomalies</p>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={anomalies}
        isLoading={loading}
        searchPlaceholder="Search by student ID..."
        searchColumn="student_id"
      />
    </div>
  )
}
