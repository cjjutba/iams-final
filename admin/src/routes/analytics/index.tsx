import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Users,
  GraduationCap,
  Calendar,
  ClipboardList,
  TrendingUp,
  ArrowRight,
  UserX,
} from 'lucide-react'
import { toast } from 'sonner'
import { usePageTitle } from '@/hooks/use-page-title'

import { StatCard, LineChartCard } from '@/components/charts'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useSystemMetrics, useDailyTrend } from '@/hooks/use-queries'

export default function AnalyticsPage() {
  usePageTitle('Analytics')
  const { data: metrics, isLoading: loading, error } = useSystemMetrics()
  const { data: trendRaw, isLoading: trendLoading } = useDailyTrend(30)

  useEffect(() => {
    if (error) toast.error('Failed to load system metrics')
  }, [error])

  const trendData = Array.isArray(trendRaw)
    ? trendRaw.map((d: Record<string, unknown>) => ({
        date: new Date(d.date as string).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
        }),
        present: (d.present ?? d.present_count ?? 0) as number,
        late: (d.late ?? d.late_count ?? 0) as number,
        early_leave: (d.early_leave ?? d.early_leave_count ?? 0) as number,
        absent: (d.absent ?? d.absent_count ?? 0) as number,
      }))
    : []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Analytics Dashboard</h1>
        <p className="text-muted-foreground">System-wide metrics and insights</p>
      </div>

      {/* System Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
        {loading ? (
          // Mirror StatCard: rounded-xl wrapper, uppercase label + 4×4 icon
          // on top row, large value below.
          Array.from({ length: 5 }).map((_, i) => (
            <div
              key={`stat-skeleton-${String(i)}`}
              className="flex flex-col gap-1 rounded-xl border border-border bg-card px-5 py-4"
            >
              <div className="flex items-center justify-between">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-4 w-4 rounded-sm" />
              </div>
              <Skeleton className="mt-1 h-8 w-20" />
            </div>
          ))
        ) : metrics ? (
          <>
            <StatCard title="Total Students" value={metrics.total_students} icon={Users} />
            <StatCard title="Total Faculty" value={metrics.total_faculty} icon={GraduationCap} />
            <StatCard title="Total Schedules" value={metrics.total_schedules} icon={Calendar} />
            <StatCard title="Total Records" value={metrics.total_attendance_records} icon={ClipboardList} />
            <StatCard
              title="Avg Attendance Rate"
              value={`${metrics.average_attendance_rate.toFixed(1)}%`}
              icon={TrendingUp}
            />
          </>
        ) : null}
      </div>

      {/* Quick Links */}
      <div className="grid grid-cols-1 gap-4">
        <Link to="/analytics/at-risk">
          <Card className="hover:border-primary/50 transition-colors cursor-pointer">
            <CardHeader className="flex flex-row items-center gap-3">
              <UserX className="h-8 w-8 text-red-600 dark:text-red-400" />
              <div className="flex-1">
                <CardTitle className="text-lg">At-Risk Students</CardTitle>
                <CardDescription>
                  Students with low attendance rates that need attention
                </CardDescription>
              </div>
              <ArrowRight className="h-5 w-5 text-muted-foreground" />
            </CardHeader>
          </Card>
        </Link>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-4">
        {trendLoading ? (
          <Card>
            <CardHeader className="pb-2">
              <Skeleton className="h-5 w-44" />
              <Skeleton className="mt-1.5 h-3 w-64" />
            </CardHeader>
            <CardContent>
              <div className="relative h-[320px] w-full">
                {/* Y-axis ticks */}
                <div className="absolute left-0 top-0 flex h-full w-8 flex-col justify-between py-1">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-2 w-6" />
                  ))}
                </div>
                {/* Plot area */}
                <Skeleton className="ml-10 h-[290px] w-[calc(100%-2.5rem)] rounded-md" />
                {/* X-axis tick row */}
                <div className="ml-10 mt-1 flex w-[calc(100%-2.5rem)] items-center justify-between">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-2 w-8" />
                  ))}
                </div>
              </div>
              {/* Legend strip */}
              <div className="mt-3 flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-1.5">
                    <Skeleton className="h-2 w-2 rounded-full" />
                    <Skeleton className="h-3 w-16" />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ) : (
          <LineChartCard
            title="Attendance Trend"
            description="Daily attendance over the last 30 days"
            data={trendData}
            xKey="date"
            lines={[
              { key: 'present', label: 'Present', color: 'var(--color-status-present)' },
              { key: 'late', label: 'Late', color: 'var(--color-status-late)' },
              { key: 'early_leave', label: 'Early Leave', color: 'var(--color-status-early-leave)' },
              { key: 'absent', label: 'Absent', color: 'var(--color-status-absent)' },
            ]}
            height={320}
          />
        )}
      </div>
    </div>
  )
}
