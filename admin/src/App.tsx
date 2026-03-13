import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth.store'
import { ProtectedRoute } from '@/components/protected-route'
import { DashboardLayout } from '@/components/layout/dashboard-layout'

const LoginPage = lazy(() => import('@/routes/login'))
const DashboardPage = lazy(() => import('@/routes/dashboard'))
const UsersPage = lazy(() => import('@/routes/users/index'))
const UserDetailPage = lazy(() => import('@/routes/users/[id]'))
const SchedulesPage = lazy(() => import('@/routes/schedules/index'))
const ScheduleDetailPage = lazy(() => import('@/routes/schedules/[id]'))
const RoomsPage = lazy(() => import('@/routes/rooms'))
const AttendancePage = lazy(() => import('@/routes/attendance'))
const AnalyticsPage = lazy(() => import('@/routes/analytics/index'))
const AtRiskPage = lazy(() => import('@/routes/analytics/at-risk'))
const AnomaliesPage = lazy(() => import('@/routes/analytics/anomalies'))
const FaceRegistrationsPage = lazy(() => import('@/routes/face-registrations'))
const EarlyLeavesPage = lazy(() => import('@/routes/early-leaves'))
const NotificationsPage = lazy(() => import('@/routes/notifications'))
const EdgeDevicesPage = lazy(() => import('@/routes/edge-devices'))
const AuditLogsPage = lazy(() => import('@/routes/audit-logs'))
const SettingsPage = lazy(() => import('@/routes/settings'))

function LoadingFallback() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
    </div>
  )
}

export default function App() {
  const checkAuth = useAuthStore((s) => s.checkAuth)

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  return (
    <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, '')}>
      <Suspense fallback={<LoadingFallback />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <ProtectedRoute>
                <DashboardLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="users/:id" element={<UserDetailPage />} />
            <Route path="schedules" element={<SchedulesPage />} />
            <Route path="schedules/:id" element={<ScheduleDetailPage />} />
            <Route path="rooms" element={<RoomsPage />} />
            <Route path="attendance" element={<AttendancePage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="analytics/at-risk" element={<AtRiskPage />} />
            <Route path="analytics/anomalies" element={<AnomaliesPage />} />
            <Route path="face-registrations" element={<FaceRegistrationsPage />} />
            <Route path="early-leaves" element={<EarlyLeavesPage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="edge-devices" element={<EdgeDevicesPage />} />
            <Route path="audit-logs" element={<AuditLogsPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
