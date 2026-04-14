import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth.store'
import { ProtectedRoute } from '@/components/protected-route'
import { DashboardLayout } from '@/components/layout/dashboard-layout'
import { Toaster } from '@/components/ui/sonner'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000,      // 2 min — data stays fresh, no refetch
      gcTime: 10 * 60 * 1000,         // 10 min — keep in cache after unmount
      refetchOnWindowFocus: false,     // don't refetch on tab switch
      retry: 1,
    },
  },
})

const LandingPage = lazy(() => import('@/routes/landing'))
const LoginPage = lazy(() => import('@/routes/login'))
const EmailConfirmedPage = lazy(() => import('@/routes/auth/email-confirmed'))
const DashboardPage = lazy(() => import('@/routes/dashboard'))
const StudentsPage = lazy(() => import('@/routes/users/students'))
const StudentRecordDetailPage = lazy(() => import('@/routes/users/student-record-detail'))
const FacultyPage = lazy(() => import('@/routes/users/faculty'))
const AdminsPage = lazy(() => import('@/routes/users/admins'))
const UserDetailPage = lazy(() => import('@/routes/users/[id]'))
const SchedulesPage = lazy(() => import('@/routes/schedules/index'))
const ScheduleDetailPage = lazy(() => import('@/routes/schedules/[id]'))
const RoomsPage = lazy(() => import('@/routes/rooms/index'))
const RoomDetailPage = lazy(() => import('@/routes/rooms/[id]'))
const AttendancePage = lazy(() => import('@/routes/attendance'))
const AnalyticsPage = lazy(() => import('@/routes/analytics/index'))
const AtRiskPage = lazy(() => import('@/routes/analytics/at-risk'))
const AnomaliesPage = lazy(() => import('@/routes/analytics/anomalies'))
const FaceRegistrationsPage = lazy(() => import('@/routes/face-registrations'))
const EarlyLeavesPage = lazy(() => import('@/routes/early-leaves'))
const NotificationsPage = lazy(() => import('@/routes/notifications'))
const EdgeDevicesPage = lazy(() => import('@/routes/edge-devices/index'))
const EdgeDeviceDetailPage = lazy(() => import('@/routes/edge-devices/[id]'))
const AuditLogsPage = lazy(() => import('@/routes/audit-logs'))
const SettingsPage = lazy(() => import('@/routes/settings'))

function LoadingFallback() {
  return (
    <div className="flex h-screen items-center justify-center">
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
    <QueryClientProvider client={queryClient}>
      <Toaster />
      <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, '')}>
        <Suspense fallback={<LoadingFallback />}>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/auth/email-confirmed" element={<EmailConfirmedPage />} />
            <Route
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="students" element={<StudentsPage />} />
              <Route path="students/:studentId" element={<StudentRecordDetailPage />} />
              <Route path="faculty" element={<FacultyPage />} />
              <Route path="admins" element={<AdminsPage />} />
              <Route path="users/:id" element={<UserDetailPage />} />
              <Route path="schedules" element={<SchedulesPage />} />
              <Route path="schedules/:id" element={<ScheduleDetailPage />} />
              <Route path="rooms" element={<RoomsPage />} />
              <Route path="rooms/:id" element={<RoomDetailPage />} />
              <Route path="attendance" element={<AttendancePage />} />
              <Route path="analytics" element={<AnalyticsPage />} />
              <Route path="analytics/at-risk" element={<AtRiskPage />} />
              <Route path="analytics/anomalies" element={<AnomaliesPage />} />
              <Route path="face-registrations" element={<FaceRegistrationsPage />} />
              <Route path="early-leaves" element={<EarlyLeavesPage />} />
              <Route path="notifications" element={<NotificationsPage />} />
              <Route path="edge-devices" element={<EdgeDevicesPage />} />
              <Route path="edge-devices/:id" element={<EdgeDeviceDetailPage />} />
              <Route path="audit-logs" element={<AuditLogsPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
