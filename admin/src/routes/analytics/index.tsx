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
          Array.from({ length: 5 }).map((_, i) => (
            <Card key={`skeleton-${String(i)}`}>
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
              <UserX className="h-8 w-8 text-red-500" />
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
            <CardHeader>
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-4 w-64 mt-1" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-[320px] w-full" />
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
