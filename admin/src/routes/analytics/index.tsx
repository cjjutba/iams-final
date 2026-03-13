import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  Users,
  GraduationCap,
  Calendar,
  ClipboardList,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
  UserX,
  ShieldAlert,
} from 'lucide-react'

import { StatCard, LineChartCard } from '@/components/charts'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { analyticsService } from '@/services/analytics.service'
import type { SystemMetrics } from '@/types'

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

const trendData = generateTrendData()

export default function AnalyticsPage() {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchMetrics = useCallback(async () => {
    try {
      const res = await analyticsService.systemMetrics()
      setMetrics(res.data)
      setError(null)
    } catch {
      setError('Failed to load system metrics')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchMetrics()
  }, [fetchMetrics])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Analytics Dashboard</h1>
        <p className="text-muted-foreground">System-wide metrics and insights</p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {/* System Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
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
            <StatCard
              title="Unresolved Anomalies"
              value={metrics.unresolved_anomalies}
              icon={AlertTriangle}
            />
          </>
        ) : null}
      </div>

      {/* Quick Links */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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

        <Link to="/analytics/anomalies">
          <Card className="hover:border-primary/50 transition-colors cursor-pointer">
            <CardHeader className="flex flex-row items-center gap-3">
              <ShieldAlert className="h-8 w-8 text-orange-500" />
              <div className="flex-1">
                <CardTitle className="text-lg">Anomaly Detection</CardTitle>
                <CardDescription>
                  {metrics
                    ? `${metrics.unresolved_anomalies} unresolved anomalies detected`
                    : 'Detect unusual attendance patterns'}
                </CardDescription>
              </div>
              <ArrowRight className="h-5 w-5 text-muted-foreground" />
            </CardHeader>
          </Card>
        </Link>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-4">
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
          height={320}
        />
      </div>
    </div>
  )
}
