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
    // Backend sends flat payloads: { type: "notification", notification_type: "early_leave", title, message, ... }
    const eventType = message.notification_type || message.type

    switch (eventType) {
      case 'early_leave':
        useNotificationStore.getState().incrementUnreadCount()
        toast.warning('Early Leave Detected', {
          description: message.student_name
            ? `${message.student_name} left ${message.subject_code} early`
            : message.message,
          duration: 8000,
        })
        break

      case 'early_leave_return':
        toast.success('Student Returned', {
          description: message.student_name
            ? `${message.student_name} returned to class`
            : message.message,
        })
        break

      case 'check_in':
        toast(`${message.student_name || 'Student'} checked in`, {
          description: message.subject_code
            ? `${message.subject_code} \u2014 ${message.status}`
            : message.message,
        })
        break

      case 'session_start':
        toast.info('Session Started', {
          description: message.subject_code
            ? `${message.subject_code} \u2014 ${message.subject_name}`
            : message.message,
        })
        break

      case 'session_end':
        toast.info('Session Ended', {
          description: message.subject_code
            ? `${message.subject_code} \u2014 ${message.subject_name}`
            : message.message,
        })
        break

      case 'anomaly_alert':
        useNotificationStore.getState().incrementUnreadCount()
        toast.error('Anomaly Detected', {
          description: message.anomaly_type
            ? `${message.anomaly_type}: ${message.student_name} (${message.severity})`
            : message.message,
          duration: 10000,
        })
        break

      case 'low_attendance_warning':
        useNotificationStore.getState().incrementUnreadCount()
        toast.warning('Low Attendance Warning', {
          description: message.subject_name
            ? `${message.subject_name}: ${message.current_rate}% (threshold: ${message.threshold}%)`
            : message.message,
        })
        break

      default:
        if (message.type === 'notification') {
          useNotificationStore.getState().incrementUnreadCount()
          toast.info(message.title || 'New Notification', {
            description: message.message,
          })
        }
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
