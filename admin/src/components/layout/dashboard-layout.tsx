import { Suspense, useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { SidebarProvider, SidebarInset } from '@/components/ui/sidebar'
import { AppSidebar } from './app-sidebar'
import { Header } from './header'
import { useWebSocket } from '@/hooks/use-websocket'
import { useNotificationStore } from '@/stores/notification.store'

/**
 * Visible fallback for the inner Suspense that wraps route-level lazy imports.
 * The sidebar + header are already mounted by this point, so we only need to
 * fill the content pane. An empty div (the previous fallback) made the app
 * look dead after login while Vite compiled the Dashboard chunk in dev.
 */
function RouteFallback() {
  return (
    <div className="flex h-[calc(100vh-8rem)] items-center justify-center text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin" />
      <span className="ml-2 text-sm">Loading…</span>
    </div>
  )
}

type ToastVariant = 'success' | 'warning' | 'error' | 'info'

function pickToastVariant(
  toastType: string | undefined,
  severity: string | undefined,
): ToastVariant {
  if (toastType === 'success' || toastType === 'error' || toastType === 'info') {
    return toastType
  }
  if (toastType === 'warn' || toastType === 'warning') return 'warning'
  // Fall back to severity if toast_type is missing/unknown.
  if (severity === 'critical' || severity === 'error') return 'error'
  if (severity === 'warn') return 'warning'
  if (severity === 'success') return 'success'
  return 'info'
}

function showToast(variant: ToastVariant, title: string, description?: string, duration?: number) {
  const opts: { description?: string; duration?: number } = {}
  if (description) opts.description = description
  if (duration) opts.duration = duration
  switch (variant) {
    case 'success':
      toast.success(title, opts)
      break
    case 'warning':
      toast.warning(title, opts)
      break
    case 'error':
      toast.error(title, opts)
      break
    case 'info':
    default:
      toast.info(title, opts)
      break
  }
}

interface NotificationWsPayload {
  type?: string
  notification_type?: string
  toast_type?: string
  severity?: string
  title?: string
  message?: string
  // Legacy/extra fields surfaced by individual notification types — kept
  // available so we can still render rich descriptions for known types.
  student_name?: string
  subject_code?: string
  subject_name?: string
  status?: string
  current_rate?: number | string
  threshold?: number | string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

export function DashboardLayout() {
  const { fetchUnreadCount } = useNotificationStore()

  useEffect(() => { fetchUnreadCount() }, [fetchUnreadCount])

  useWebSocket((rawMessage) => {
    if (!isRecord(rawMessage)) return
    const message = rawMessage as NotificationWsPayload

    // Only handle notification-shaped events here. Other event types
    // (e.g. attendance_update broadcasts on the attendance WS) come in
    // via their own dedicated hooks; if they show up on this socket we
    // ignore them rather than guess.
    if (message.type !== 'notification') return

    const severity = (message.severity ?? 'info') as string
    const eventType = message.notification_type || ''
    const variant = pickToastVariant(message.toast_type, severity)

    // Centralized: every notification event bumps the unread badge.
    // (Previously only 3 of 7 known event types did this — the bug
    // that left the bell stuck at zero for camera/security/etc.)
    useNotificationStore.getState().incrementUnreadCount()
    if (severity === 'critical' || severity === 'error') {
      useNotificationStore.getState().incrementCriticalCount()
    }

    // Build a description: prefer the rich per-type wording when we
    // recognise the event, else fall back to the generic message body.
    let description: string | undefined = message.message
    let duration: number | undefined
    switch (eventType) {
      case 'early_leave':
        description = message.student_name && message.subject_code
          ? `${message.student_name} left ${message.subject_code} early`
          : message.message
        duration = 8000
        break
      case 'early_leave_return':
        description = message.student_name
          ? `${message.student_name} returned to class`
          : message.message
        break
      case 'check_in':
        description = message.subject_code
          ? `${message.subject_code} — ${message.status ?? ''}`.trim()
          : message.message
        break
      case 'session_start':
      case 'session_end':
        description = message.subject_code
          ? `${message.subject_code} — ${message.subject_name ?? ''}`.trim()
          : message.message
        break
      case 'low_attendance_warning':
        description = message.subject_name
          ? `${message.subject_name}: ${message.current_rate}% (threshold: ${message.threshold}%)`
          : message.message
        break
      default:
        description = message.message
        break
    }

    const title =
      message.title ||
      (eventType === 'check_in' && message.student_name
        ? `${message.student_name} checked in`
        : 'New Notification')

    showToast(variant, title, description, duration)
  })

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <Header />
        <main className="flex-1 p-6">
          <div className="mx-auto w-full max-w-[1440px]">
            <Suspense fallback={<RouteFallback />}>
              <Outlet />
            </Suspense>
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
