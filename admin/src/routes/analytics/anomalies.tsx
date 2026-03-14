import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { format } from 'date-fns'
import { ArrowLeft, CheckCircle, Loader2 } from 'lucide-react'
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
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useAnomalies, useResolveAnomaly } from '@/hooks/use-queries'
import type { AttendanceAnomaly } from '@/types'
import { formatStatus } from '@/types/attendance'

function AnomalyActions({ anomaly }: { anomaly: AttendanceAnomaly }) {
  const [open, setOpen] = useState(false)
  const resolveAnomaly = useResolveAnomaly()

  if (anomaly.resolved) {
    return <Badge className="bg-green-100 text-green-800 hover:bg-green-100">Resolved</Badge>
  }

  const handleResolve = async () => {
    try {
      await resolveAnomaly.mutateAsync(anomaly.id)
      toast.success('Anomaly marked as resolved')
    } catch {
      toast.error('Failed to resolve anomaly')
    } finally {
      setOpen(false)
    }
  }

  return (
    <>
      <Button variant="outline" size="sm" disabled={resolveAnomaly.isPending} onClick={() => setOpen(true)}>
        {resolveAnomaly.isPending ? (
          <><Loader2 className="mr-1 h-3 w-3 animate-spin" />Resolving...</>
        ) : (
          <><CheckCircle className="mr-1 h-3 w-3" />Resolve</>
        )}
      </Button>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Resolve Anomaly</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to mark this anomaly as resolved? This action indicates the issue has been reviewed.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={resolveAnomaly.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                void handleResolve()
              }}
              disabled={resolveAnomaly.isPending}
            >
              {resolveAnomaly.isPending ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Resolving...</>) : 'Resolve'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

const anomalyTypeLabels: Record<string, string> = {
  sudden_absence: 'Sudden Absence',
  proxy_suspect: 'Proxy Suspect',
  pattern_break: 'Pattern Break',
  low_confidence: 'Low Confidence',
}

export default function AnomaliesPage() {
  usePageTitle('Anomalies')
  const navigate = useNavigate()
  const { data: anomalies = [], isLoading } = useAnomalies()

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
          {anomalyTypeLabels[row.original.anomaly_type] ?? formatStatus(row.original.anomaly_type)}
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
        <AnomalyActions anomaly={row.original} />
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
          <h1 className="text-2xl font-semibold tracking-tight">Anomaly Detection</h1>
          <p className="text-muted-foreground">Review and resolve attendance anomalies</p>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={anomalies}
        isLoading={isLoading}
        searchPlaceholder="Search by student ID..."
        searchColumn="student_id"
        onRowClick={(row) => navigate(`/users/${row.student_id}`, { state: { role: 'student' } })}
      />
    </div>
  )
}
