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
import { Skeleton } from '@/components/ui/skeleton'
import { LiveNowPill } from '@/components/shared/status-pills'
import { useSystemMetrics, useScheduleSummaries, useDailyTrend, useWeekdayBreakdown } from '@/hooks/use-queries'
import type { ScheduleAttendanceSummary } from '@/types'

// Single tinted-pill rule for attendance rate, matching the colored
// outline pill family used across the rest of the admin (`AttendanceStatusPill`,
// `RuntimeStatusPill`, etc.). Rate >= 85 is healthy, 70-84 is warning,
// below 70 is concerning. Same thresholds as the per-record presence
// score color in `attendance.tsx`.
function AttendanceRatePill({ rate }: { rate: number }) {
  const tone =
    rate >= 85
      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
      : rate >= 70
        ? 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400'
        : 'border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400'
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${tone}`}
    >
      {rate.toFixed(0)}%
    </span>
  )
}

// --- Table columns ---

const sessionColumns: ColumnDef<ScheduleAttendanceSummary>[] = [
  {
    accessorKey: 'subject_name',
    header: 'Subject',
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        <span className="font-medium">{row.original.subject_name}</span>
        <LiveNowPill />
      </div>
    ),
  },
  { accessorKey: 'room_name', header: 'Room', cell: ({ row }) => row.original.room_name ?? '—' },
  {
    accessorKey: 'total_enrolled',
    header: 'Enrolled',
    cell: ({ row }) => (
      <span className="text-sm tabular-nums">{row.original.total_enrolled}</span>
    ),
  },
  {
    accessorKey: 'present_count',
    header: 'Present',
    cell: ({ row }) => (
      <span className="text-sm tabular-nums">{row.original.present_count}</span>
    ),
  },
  {
    accessorKey: 'attendance_rate',
    header: 'Rate',
    cell: ({ row }) => <AttendanceRatePill rate={row.original.attendance_rate} />,
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
              { key: 'present', label: 'Present', color: 'var(--color-status-present)' },
              { key: 'late', label: 'Late', color: 'var(--color-status-late)' },
              { key: 'early_leave', label: 'Early Leave', color: 'var(--color-status-early-leave)' },
              { key: 'absent', label: 'Absent', color: 'var(--color-status-absent)' },
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
