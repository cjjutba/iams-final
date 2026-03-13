import { useState, useEffect, useCallback } from 'react'
import { type ColumnDef } from '@tanstack/react-table'
import {
  Users,
  GraduationCap,
  Calendar,
  ClipboardList,
  TrendingUp,
  DoorOpen,
} from 'lucide-react'

import { StatCard, LineChartCard, BarChartCard } from '@/components/charts'
import { DataTable } from '@/components/data-tables'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { analyticsService } from '@/services/analytics.service'
import { attendanceService } from '@/services/attendance.service'
import type { SystemMetrics, ScheduleAttendanceSummary, EarlyLeaveAlert } from '@/types'

// --- Mock chart data ---

function generateTrendData() {
  const data: Record<string, unknown>[] = []
  const now = new Date()
  for (let i = 29; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    const label = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    data.push({
      date: label,
      present: Math.floor(70 + Math.random() * 25),
      late: Math.floor(5 + Math.random() * 10),
      absent: Math.floor(3 + Math.random() * 8),
    })
  }
  return data
}

const WEEKDAY_DATA = [
  { day: 'Mon', rate: 88 },
  { day: 'Tue', rate: 91 },
  { day: 'Wed', rate: 85 },
  { day: 'Thu', rate: 90 },
  { day: 'Fri', rate: 78 },
  { day: 'Sat', rate: 62 },
  { day: 'Sun', rate: 0 },
]

const trendData = generateTrendData()

// --- Table columns ---

const sessionColumns: ColumnDef<ScheduleAttendanceSummary>[] = [
  { accessorKey: 'subject_name', header: 'Subject' },
  { accessorKey: 'room_name', header: 'Room', cell: ({ row }) => row.original.room_name ?? '—' },
  { accessorKey: 'total_enrolled', header: 'Enrolled' },
  { accessorKey: 'present_count', header: 'Present' },
  {
    accessorKey: 'attendance_rate',
    header: 'Rate',
    cell: ({ row }) => (
      <Badge variant={row.original.attendance_rate >= 75 ? 'default' : 'destructive'}>
        {row.original.attendance_rate.toFixed(0)}%
      </Badge>
    ),
  },
]

const alertColumns: ColumnDef<EarlyLeaveAlert>[] = [
  { accessorKey: 'student_name', header: 'Student' },
  { accessorKey: 'subject_name', header: 'Subject' },
  {
    accessorKey: 'detected_at',
    header: 'Time',
    cell: ({ row }) => {
      const dt = new Date(row.original.detected_at)
      return dt.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    },
  },
  {
    accessorKey: 'consecutive_misses',
    header: 'Misses',
    cell: ({ row }) => (
      <Badge variant={row.original.consecutive_misses >= 3 ? 'destructive' : 'secondary'}>
        {row.original.consecutive_misses}
      </Badge>
    ),
  },
]

// --- Component ---

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null)
  const [metricsLoading, setMetricsLoading] = useState(true)
  const [metricsError, setMetricsError] = useState<string | null>(null)

  const [sessions, setSessions] = useState<ScheduleAttendanceSummary[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(true)

  const [alerts, setAlerts] = useState<EarlyLeaveAlert[]>([])
  const [alertsLoading, setAlertsLoading] = useState(true)

  const fetchMetrics = useCallback(async () => {
    try {
      const res = await analyticsService.systemMetrics()
      setMetrics(res.data)
      setMetricsError(null)
    } catch {
      setMetricsError('Failed to load metrics')
    } finally {
      setMetricsLoading(false)
    }
  }, [])

  const fetchSessions = useCallback(async () => {
    try {
      const data = await attendanceService.getScheduleSummaries()
      setSessions(data.filter((s) => s.session_active))
    } catch {
      // silently handle
    } finally {
      setSessionsLoading(false)
    }
  }, [])

  const fetchAlerts = useCallback(async () => {
    try {
      const data = await attendanceService.getAlerts()
      setAlerts(data.slice(0, 5))
    } catch {
      // silently handle
    } finally {
      setAlertsLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchMetrics()
    void fetchSessions()
    void fetchAlerts()

    const interval = setInterval(() => {
      void fetchMetrics()
    }, 60_000)

    return () => clearInterval(interval)
  }, [fetchMetrics, fetchSessions, fetchAlerts])

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">System overview and real-time monitoring</p>
      </div>

      {/* Stat cards */}
      {metricsError && (
        <p className="text-sm text-destructive">{metricsError}</p>
      )}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        {metricsLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
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
        ) : metrics ? (
          <>
            <StatCard title="Total Students" value={metrics.total_students} icon={Users} />
            <StatCard title="Total Faculty" value={metrics.total_faculty} icon={GraduationCap} />
            <StatCard title="Active Schedules" value={metrics.total_schedules} icon={Calendar} />
            <StatCard title="Attendance Records" value={metrics.total_attendance_records} icon={ClipboardList} />
            <StatCard
              title="Avg Attendance Rate"
              value={`${metrics.average_attendance_rate.toFixed(1)}%`}
              icon={TrendingUp}
            />
            <StatCard title="Early Leaves" value={metrics.total_early_leaves} icon={DoorOpen} />
          </>
        ) : null}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <LineChartCard
          title="Attendance Trend"
          description="Daily attendance over the last 30 days"
          data={trendData}
          xKey="date"
          lines={[
            { key: 'present', label: 'Present', color: 'var(--color-chart-1)' },
            { key: 'late', label: 'Late', color: 'var(--color-chart-3)' },
            { key: 'absent', label: 'Absent', color: 'var(--color-chart-5)' },
          ]}
          height={280}
        />
        <BarChartCard
          title="Attendance by Weekday"
          description="Average attendance rate per day of the week"
          data={WEEKDAY_DATA}
          xKey="day"
          bars={[{ key: 'rate', label: 'Attendance Rate (%)', color: 'var(--color-chart-2)' }]}
          height={280}
        />
      </div>

      {/* Tables row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Active Sessions</CardTitle>
          </CardHeader>
          <CardContent>
            <DataTable
              columns={sessionColumns}
              data={sessions}
              isLoading={sessionsLoading}
              pageSize={5}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Early Leave Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            <DataTable
              columns={alertColumns}
              data={alerts}
              isLoading={alertsLoading}
              pageSize={5}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
