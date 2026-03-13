import { useState, useEffect, useCallback } from 'react'
import { type ColumnDef } from '@tanstack/react-table'
import { ScanFace, UserCheck, UserX, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { StatCard } from '@/components/charts'
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
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { faceService } from '@/services/face.service'
import { usersService } from '@/services/users.service'
import type { UserResponse, FaceStatistics } from '@/types'

function DeregisterAction({ user, onDeregistered }: { user: UserResponse; onDeregistered: () => void }) {
  const [loading, setLoading] = useState(false)

  const handleDeregister = async () => {
    setLoading(true)
    try {
      await faceService.deregister(user.id)
      toast.success(`Face deregistered for ${user.first_name} ${user.last_name}`)
      onDeregistered()
    } catch {
      toast.error('Failed to deregister face')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="outline" size="sm" disabled={loading}>
          <Trash2 className="mr-1 h-3 w-3" />
          Deregister
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Deregister Face</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to remove the face registration for {user.first_name} {user.last_name}? They will need to re-register their face to use the system.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={() => void handleDeregister()}>Deregister</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export default function FaceRegistrationsPage() {
  const [students, setStudents] = useState<UserResponse[]>([])
  const [stats, setStats] = useState<FaceStatistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [statsLoading, setStatsLoading] = useState(true)

  const fetchStudents = useCallback(async () => {
    try {
      const data = await usersService.list({ role: 'student' })
      setStudents(data)
    } catch {
      toast.error('Failed to load students')
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchStats = useCallback(async () => {
    try {
      const res = await faceService.statistics()
      setStats(res.data)
    } catch {
      // silently handle
    } finally {
      setStatsLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchStudents()
    void fetchStats()
  }, [fetchStudents, fetchStats])

  const handleRefresh = () => {
    void fetchStudents()
    void fetchStats()
  }

  const columns: ColumnDef<UserResponse>[] = [
    {
      accessorKey: 'first_name',
      header: 'Student Name',
      cell: ({ row }) => `${row.original.first_name} ${row.original.last_name}`,
    },
    {
      accessorKey: 'student_id',
      header: 'Student ID',
      cell: ({ row }) => row.original.student_id ?? '—',
    },
    {
      accessorKey: 'is_active',
      header: 'Status',
      cell: ({ row }) => (
        <Badge className={row.original.is_active
          ? 'bg-green-100 text-green-800 hover:bg-green-100'
          : 'bg-gray-100 text-gray-800 hover:bg-gray-100'
        }>
          {row.original.is_active ? 'Active' : 'Inactive'}
        </Badge>
      ),
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => (
        <DeregisterAction user={row.original} onDeregistered={handleRefresh} />
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Face Registration Management</h1>
        <p className="text-muted-foreground">Manage student face registrations</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {statsLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <Card key={`stat-skeleton-${String(i)}`}>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-4" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-7 w-16" />
              </CardContent>
            </Card>
          ))
        ) : stats ? (
          <>
            <StatCard title="Total Registered" value={stats.total_registered} icon={ScanFace} />
            <StatCard title="Active" value={stats.total_active} icon={UserCheck} />
            <StatCard title="Inactive" value={stats.total_inactive} icon={UserX} />
          </>
        ) : null}
      </div>

      <DataTable
        columns={columns}
        data={students}
        isLoading={loading}
        searchPlaceholder="Search students..."
        searchColumn="first_name"
      />
    </div>
  )
}
