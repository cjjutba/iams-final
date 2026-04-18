import { useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { usePageTitle } from '@/hooks/use-page-title'
import {
  Users,
  GraduationCap,
  Calendar,
  TrendingUp,
} from 'lucide-react'

import { toast } from 'sonner'
import { StatCard, LineChartCard, BarChartCard } from '@/components/charts'
import { DataTable } from '@/components/data-tables'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useSystemMetrics, useScheduleSummaries, useDailyTrend, useWeekdayBreakdown } from '@/hooks/use-queries'
import type { ScheduleAttendanceSummary } from '@/types'

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

// --- Component ---

export default function DashboardPage() {
  usePageTitle('Dashboard')
  const navigate = useNavigate()
  const { data: metrics, isLoading: metricsLoading, error: metricsError } = useSystemMetrics()
  const { data: summaries = [], isLoading: sessionsLoading } = useScheduleSummaries()
  const { data: trendData = [], isLoading: trendLoading } = useDailyTrend(30)
  const { data: weekdayData = [], isLoading: weekdayLoading } = useWeekdayBreakdown()

  useEffect(() => {
    if (metricsError) toast.error('Failed to load metrics')
  }, [metricsError])

  const sessions = useMemo(() => summaries.filter((s) => s.session_active), [summaries])

  // Format trend dates for display
  const formattedTrend = useMemo(
    () =>
      trendData.map((item) => ({
        ...item,
        date: new Date(item.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      })),
    [trendData],
  )

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">System overview and real-time monitoring</p>
      </div>

      {/* Stat cards — 4 cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {metricsLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={`stat-skeleton-${String(i)}`} className="rounded-xl border border-border bg-card px-5 py-4 space-y-2">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-7 w-14" />
            </div>
          ))
        ) : metrics ? (
          <>
            <StatCard title="Students" value={metrics.total_students} icon={Users} />
            <StatCard title="Faculty" value={metrics.total_faculty} icon={GraduationCap} />
            <StatCard title="Schedules" value={metrics.total_schedules} icon={Calendar} />
            <StatCard
              title="Avg Attendance"
              value={`${metrics.average_attendance_rate.toFixed(1)}%`}
              icon={TrendingUp}
            />
          </>
        ) : null}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {trendLoading ? (
          <div className="rounded-xl border border-border bg-card p-6 space-y-4">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-[280px] w-full" />
          </div>
        ) : (
          <LineChartCard
            title="Attendance Trend"
            description="Daily attendance over the last 30 days"
            data={formattedTrend}
            xKey="date"
            lines={[
              { key: 'present', label: 'Present', color: 'var(--color-chart-1)' },
              { key: 'late', label: 'Late', color: 'var(--color-chart-3)' },
              { key: 'early_leave', label: 'Early Leave', color: 'var(--color-chart-4)' },
              { key: 'absent', label: 'Absent', color: 'var(--color-chart-5)' },
            ]}
            height={280}
          />
        )}
        {weekdayLoading ? (
          <div className="rounded-xl border border-border bg-card p-6 space-y-4">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-[280px] w-full" />
          </div>
        ) : (
          <BarChartCard
            title="Attendance by Weekday"
            description="Average attendance rate per day of the week"
            data={weekdayData}
            xKey="day"
            bars={[{ key: 'rate', label: 'Attendance Rate (%)', color: 'var(--color-chart-2)' }]}
            height={280}
          />
        )}
      </div>

      {/* Active Sessions — full width */}
      <div className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground tracking-wide uppercase">Active Sessions</h2>
        <DataTable
          columns={sessionColumns}
          data={sessions}
          isLoading={sessionsLoading}
          pageSize={5}
          onRowClick={(row) => navigate(`/schedules/${row.schedule_id}`)}
        />
      </div>
    </div>
  )
}
