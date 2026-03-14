import { Suspense, useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { toast } from 'sonner'
import { SidebarProvider, SidebarInset } from '@/components/ui/sidebar'
import { AppSidebar } from './app-sidebar'
import { Header } from './header'
import { useWebSocket } from '@/hooks/use-websocket'
import { useNotificationStore } from '@/stores/notification.store'

export function DashboardLayout() {
  const { fetchUnreadCount } = useNotificationStore()

  useEffect(() => { fetchUnreadCount() }, [fetchUnreadCount])

  useWebSocket((message) => {
    const event = message.event
    const data = message.data

    switch (event) {
      case 'notification':
        useNotificationStore.getState().incrementUnreadCount()
        toast.info(data?.title || 'New Notification', {
          description: data?.message,
        })
        break

      case 'early_leave':
        useNotificationStore.getState().incrementUnreadCount()
        toast.warning('Early Leave Detected', {
          description: `${data?.student_name} left ${data?.subject_code} early`,
          duration: 8000,
        })
        break

      case 'early_leave_return':
        toast.success('Student Returned', {
          description: `${data?.student_name} returned to class`,
        })
        break

      case 'attendance_update':
        toast(`${data?.student_name} checked in`, {
          description: `${data?.subject_code} \u2014 ${data?.status}`,
        })
        break

      case 'session_start':
        toast.info('Session Started', {
          description: `${data?.subject_code} \u2014 ${data?.subject_name}`,
        })
        break

      case 'session_end':
        toast.info('Session Ended', {
          description: `${data?.subject_code} \u2014 ${data?.subject_name}`,
        })
        break

      case 'anomaly_detected':
        useNotificationStore.getState().incrementUnreadCount()
        toast.error('Anomaly Detected', {
          description: `${data?.anomaly_type}: ${data?.student_name} (${data?.severity})`,
          duration: 10000,
        })
        break

      case 'low_attendance_warning':
        useNotificationStore.getState().incrementUnreadCount()
        toast.warning('Low Attendance Warning', {
          description: `${data?.subject_name}: ${data?.current_rate}% (threshold: ${data?.threshold}%)`,
        })
        break
    }
  })

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <Header />
        <main className="flex-1 p-6">
          <div className="mx-auto w-full max-w-[1440px]">
            <Suspense fallback={<div className="h-full" />}>
              <Outlet />
            </Suspense>
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
