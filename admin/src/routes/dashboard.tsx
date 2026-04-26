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
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
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

// --- Skeleton helpers ---

/**
 * Mirrors the real `LineChartCard` / `BarChartCard` shape: `Card` →
 * `CardHeader pb-2` (title + description) → `CardContent` (chart area
 * + legend strip). Same paddings, same chart height (280px), same
 * border radius — so the cut-over to a loaded chart has zero layout
 * shift.
 */
function ChartCardSkeleton({
  titleWidth,
  descriptionWidth,
  legendItems,
}: {
  titleWidth: string
  descriptionWidth: string
  legendItems: number
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <Skeleton className={`h-5 ${titleWidth}`} />
        <Skeleton className={`mt-1.5 h-3 ${descriptionWidth}`} />
      </CardHeader>
      <CardContent>
        <div className="relative h-[280px] w-full">
          {/* Y-axis ticks */}
          <div className="absolute left-0 top-0 flex h-full w-8 flex-col justify-between py-1">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-2 w-6" />
            ))}
          </div>
          {/* Plot area */}
          <Skeleton className="ml-10 h-[252px] w-[calc(100%-2.5rem)] rounded-md" />
          {/* X-axis tick row */}
          <div className="ml-10 mt-1 flex w-[calc(100%-2.5rem)] items-center justify-between">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-2 w-8" />
            ))}
          </div>
        </div>
        {/* Legend strip — matches recharts <Legend /> at the bottom */}
        <div className="mt-3 flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
          {Array.from({ length: legendItems }).map((_, i) => (
            <div key={i} className="flex items-center gap-1.5">
              <Skeleton className="h-2 w-2 rounded-full" />
              <Skeleton className="h-3 w-16" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

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
          // Mirror the real StatCard: header row (uppercase label + 4x4
          // icon on the right), then a 2xl-sized value. Same outer
          // wrapper class as the loaded card so widths/borders match.
          Array.from({ length: 4 }).map((_, i) => (
            <div
              key={`stat-skeleton-${String(i)}`}
              className="flex flex-col gap-1 rounded-xl border border-border bg-card px-5 py-4"
            >
              <div className="flex items-center justify-between">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-4 w-4 rounded-sm" />
              </div>
              <Skeleton className="mt-1 h-8 w-20" />
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
          <ChartCardSkeleton
            titleWidth="w-44"
            descriptionWidth="w-64"
            legendItems={4}
          />
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
          <ChartCardSkeleton
            titleWidth="w-52"
            descriptionWidth="w-72"
            legendItems={1}
          />
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
        {sessionsLoading ? (
          <ActiveSessionsSkeleton />
        ) : (
          <DataTable
            columns={sessionColumns}
            data={sessions}
            isLoading={false}
            pageSize={5}
            onRowClick={(row) => navigate(`/schedules/${row.schedule_id}`)}
          />
        )}
      </div>
    </div>
  )
}

/**
 * Layout-matched skeleton for the Active Sessions DataTable:
 *
 * - Same toolbar (search input, with the magnifier offset at left-2.5)
 * - Real `<Table>` + header row (Subject, Room, Enrolled, Present, Rate)
 *   so column proportions match the loaded table exactly
 * - 5 rows (matches `pageSize={5}` on the loaded DataTable) with
 *   column-shaped cells: Subject = text + LIVE NOW pill skeleton, Room =
 *   short text, Enrolled/Present = small tabular numbers, Rate =
 *   rounded-full pill
 * - Pagination footer mirroring `Showing X to Y of Z` + Rows per page +
 *   prev/next icon buttons
 */
function ActiveSessionsSkeleton() {
  return (
    <div>
      {/* Toolbar — same `py-4 flex justify-between gap-4` rhythm as
          DataTableToolbar so the search-input position doesn't shift. */}
      <div className="flex items-center justify-between gap-4 py-4">
        <Skeleton className="h-9 w-full max-w-sm rounded-md" />
      </div>

      <div className="rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Subject</TableHead>
              <TableHead>Room</TableHead>
              <TableHead>Enrolled</TableHead>
              <TableHead>Present</TableHead>
              <TableHead>Rate</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Array.from({ length: 5 }).map((_, i) => (
              <TableRow key={`active-sessions-skel-${String(i)}`}>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Skeleton className="h-4 w-48" />
                    <Skeleton className="h-5 w-20 rounded-full" />
                  </div>
                </TableCell>
                <TableCell>
                  <Skeleton className="h-4 w-16" />
                </TableCell>
                <TableCell>
                  <Skeleton className="h-4 w-6" />
                </TableCell>
                <TableCell>
                  <Skeleton className="h-4 w-6" />
                </TableCell>
                <TableCell>
                  <Skeleton className="h-5 w-12 rounded-full" />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination — same px-2 py-4 spacing as DataTablePagination. */}
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
  )
}
