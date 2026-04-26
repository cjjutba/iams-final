import { useMemo, useState, useTransition } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeftIcon, ChevronRightIcon, Inbox, SearchIcon, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { usePageTitle } from '@/hooks/use-page-title'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { notificationsService } from '@/services/notifications.service'
import { useNotificationStore } from '@/stores/notification.store'
import { NotificationRow } from '@/components/notifications/notification-row'
import { EmptyState } from '@/components/shared/empty-state'
import { tokenMatches, joinHaystack } from '@/lib/search'
import type { Notification, NotificationSeverity } from '@/types'

const SEVERITY_OPTIONS: { value: 'all' | NotificationSeverity; label: string }[] = [
  { value: 'all', label: 'All severities' },
  { value: 'info', label: 'Info' },
  { value: 'success', label: 'Success' },
  { value: 'warn', label: 'Warning' },
  { value: 'error', label: 'Error' },
  { value: 'critical', label: 'Critical' },
]

// Known notification types as of Phase 2. Future event sources should be
// added here so they're available in the type filter dropdown. Backend
// remains the source of truth — anything it sends that's not in this
// list still appears in the rendered list, just not as a filter option.
const KNOWN_TYPES = [
  'check_in',
  'late_arrival',
  'early_leave',
  'early_leave_return',
  'marked_absent_session_end',
  'session_start',
  'session_end',
  'session_auto_started',
  'session_auto_ended',
  'session_zero_recognition',
  'low_attendance_warning',
  'anomaly_alert',
  'spoof_attempt_detected',
  'unknown_person_detected',
  'auto_cctv_enroll_committed',
  'auto_cctv_swap_safe_failed',
  'system_boot',
  'liveness_unavailable',
  'scheduled_job_failed',
  'face_data_deleted',
  'admin_user_provisioned',
  'daily_digest',
  'weekly_digest',
  'daily_health_summary',
  'broadcast',
  'system',
] as const

// Category buckets matching notification_service.py emit tags. Types not
// in any bucket fall through and remain reachable via the Type dropdown.
const NOTIFICATION_CATEGORIES: Record<string, string[]> = {
  'Operational Health': [
    'camera_offline',
    'camera_recovered',
    'rtsp_connection_failed',
    'frame_stale',
    'ml_sidecar_down',
    'ml_sidecar_recovered',
    'liveness_unavailable',
    'faiss_mismatch',
    'faiss_reconcile_failed',
    'redis_connection_lost',
    'scheduled_job_failed',
  ],
  'Security & Recognition': [
    'unknown_person_detected',
    'spoof_attempt_detected',
    'face_registration_pending_review',
    'face_registration_approved',
    'face_registration_rejected',
    'face_re_registration_required',
    'face_data_deleted',
    'auto_cctv_enroll_committed',
    'auto_cctv_swap_safe_failed',
    'failed_login_burst',
    'password_changed',
    'password_reset_requested',
  ],
  'Attendance & Sessions': [
    'check_in',
    'late_arrival',
    'early_leave',
    'early_leave_return',
    'marked_absent_session_end',
    'session_start',
    'session_end',
    'session_auto_started',
    'session_auto_ended',
    'session_start_manual',
    'session_end_manual',
    'session_zero_recognition',
    'low_attendance_warning',
    'anomaly_alert',
    'anomaly_alert_admin',
  ],
  'Account & Schedule': [
    'user_created',
    'user_deactivated',
    'user_reactivated',
    'user_role_changed',
    'admin_user_provisioned',
    'schedule_assigned',
    'schedule_updated',
    'schedule_deleted',
    'schedule_conflict_warning',
    'enrollment_added',
    'enrollment_removed',
  ],
  'System': [
    'system_boot',
    'settings_changed',
    'recognition_threshold_changed',
    'daily_digest',
    'weekly_digest',
    'daily_health_summary',
    'broadcast',
    'system',
  ],
}

const CATEGORY_ORDER = [
  'Operational Health',
  'Security & Recognition',
  'Attendance & Sessions',
  'Account & Schedule',
  'System',
] as const

type ReadFilter = 'all' | 'unread' | 'read'
type SeverityFilter = 'all' | NotificationSeverity
type CategoryFilter = 'all' | (typeof CATEGORY_ORDER)[number]

const PAGE_SIZE = 20

function buildNotificationHaystack(n: Notification): string {
  return joinHaystack([n.title, n.message, n.type, n.severity])
}

export default function NotificationsPage() {
  usePageTitle('Notifications')
  const queryClient = useQueryClient()
  const { fetchUnreadCount } = useNotificationStore()

  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all')
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [readFilter, setReadFilter] = useState<ReadFilter>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [page, setPage] = useState(0)
  const [isPending, startTransition] = useTransition()

  // Server supports a single severity / single type / unread_only. We
  // request a generous batch and narrow the rest client-side so the
  // category + free-text + read=read filters can be combined freely.
  //
  // NOTE: ``limit`` MUST stay ≤ the backend cap
  // ([backend/app/routers/notifications.py:31](backend/app/routers/notifications.py#L31)
  // is currently ``le=200``). Above that the request 422s and the page
  // renders empty even though notifications exist — observed in prod
  // with ``limit=500`` (2026-04-26 fix).
  const queryParams = useMemo(
    () => ({
      severity: severityFilter !== 'all' ? severityFilter : undefined,
      type:
        categoryFilter === 'all' && typeFilter !== 'all' ? typeFilter : undefined,
      unread_only: readFilter === 'unread',
      skip: 0,
      limit: 200,
    }),
    [severityFilter, categoryFilter, typeFilter, readFilter],
  )

  const { data: notifications = [], isLoading } = useQuery({
    queryKey: ['notifications', 'page', queryParams],
    queryFn: () => notificationsService.list(queryParams),
  })

  const filtered = useMemo(() => {
    let result = notifications
    if (categoryFilter !== 'all') {
      const allowed = new Set(NOTIFICATION_CATEGORIES[categoryFilter] ?? [])
      result = result.filter((n) => allowed.has(n.type))
    }
    if (readFilter === 'read') {
      result = result.filter((n) => n.read)
    }
    if (searchQuery.trim()) {
      result = result.filter((n) => tokenMatches(buildNotificationHaystack(n), searchQuery))
    }
    return result
  }, [notifications, categoryFilter, readFilter, searchQuery])

  const totalFiltered = filtered.length
  const pageStart = page * PAGE_SIZE
  const pageEnd = Math.min(pageStart + PAGE_SIZE, totalFiltered)
  const pageItems = filtered.slice(pageStart, pageEnd)
  const hasNextPage = pageEnd < totalFiltered
  const hasPrevPage = page > 0

  const hasFilters =
    severityFilter !== 'all' ||
    categoryFilter !== 'all' ||
    typeFilter !== 'all' ||
    readFilter !== 'all' ||
    searchQuery.trim().length > 0

  function handleFilterChange<T>(setter: (v: T) => void) {
    return (value: string) => {
      startTransition(() => {
        setter(value as T)
        setPage(0)
      })
    }
  }

  function clearFilters() {
    startTransition(() => {
      setSeverityFilter('all')
      setCategoryFilter('all')
      setTypeFilter('all')
      setReadFilter('all')
      setSearchQuery('')
      setPage(0)
    })
  }

  const invalidateAll = async () => {
    await queryClient.invalidateQueries({ queryKey: ['notifications'] })
    await queryClient.invalidateQueries({ queryKey: ['notification-stats'] })
    await fetchUnreadCount()
  }

  const handleMarkAllRead = async () => {
    try {
      await notificationsService.markAllRead()
      await invalidateAll()
      toast.success('All notifications marked as read')
    } catch {
      toast.error('Failed to mark notifications as read')
    }
  }

  const handleClearAll = async () => {
    try {
      await notificationsService.removeAll()
      await invalidateAll()
      toast.success('All notifications cleared')
    } catch {
      toast.error('Failed to clear notifications')
    }
  }

  const handleMarkRead = async (notification: Notification) => {
    try {
      await notificationsService.markRead(notification.id)
      await invalidateAll()
    } catch {
      toast.error('Failed to mark notification as read')
    }
  }

  const handleDelete = async (notification: Notification) => {
    try {
      await notificationsService.remove(notification.id)
      await invalidateAll()
      toast.success('Notification deleted')
    } catch {
      toast.error('Failed to delete notification')
    }
  }

  if (isLoading) {
    // Mirror the loaded layout (header + toolbar + list + pagination) so
    // the cut-over to real data doesn't shift the page.
    return (
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-7 w-44" />
            <Skeleton className="h-4 w-56" />
          </div>
          <div className="flex items-center gap-2">
            <Skeleton className="h-9 w-32 rounded-md" />
            <Skeleton className="h-9 w-28 rounded-md" />
          </div>
        </div>

        <div>
          {/* Toolbar — search + 4 dropdowns */}
          <div className="flex items-center justify-between gap-4 py-4">
            <Skeleton className="h-9 w-full max-w-sm rounded-md" />
            <div className="flex items-center gap-2">
              <Skeleton className="h-9 w-[160px] rounded-md" />
              <Skeleton className="h-9 w-[150px] rounded-md" />
              <Skeleton className="h-9 w-[160px] rounded-md" />
              <Skeleton className="h-9 w-[140px] rounded-md" />
            </div>
          </div>

          {/* List rows */}
          <div className="rounded-lg border border-border">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={`notif-skel-${String(i)}`}
                className="flex items-start gap-3 border-b px-4 py-3 last:border-b-0"
              >
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Skeleton className="h-4 w-44" />
                    <Skeleton className="h-4 w-16 rounded-full" />
                  </div>
                  <Skeleton className="h-3 w-3/4 max-w-md" />
                  <div className="flex items-center gap-2">
                    <Skeleton className="h-3 w-20" />
                    <Skeleton className="h-3 w-28" />
                  </div>
                </div>
                <Skeleton className="h-7 w-7 rounded-md" />
              </div>
            ))}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-2 py-4">
            <Skeleton className="h-4 w-44" />
            <div className="flex items-center gap-1">
              <Skeleton className="h-8 w-8 rounded-md" />
              <Skeleton className="h-8 w-8 rounded-md" />
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Notifications</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {hasFilters
              ? `${totalFiltered} of ${notifications.length} notification${
                  notifications.length !== 1 ? 's' : ''
                }`
              : `${notifications.length} notification${notifications.length !== 1 ? 's' : ''}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleMarkAllRead}>
            Mark all read
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" className="text-destructive hover:text-destructive">
                <Trash2 className="mr-2 h-4 w-4" />
                Clear all
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Clear all notifications?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will permanently delete every notification on your account.
                  This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction variant="destructive" onClick={handleClearAll}>
                  Clear all
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between gap-4 py-4">
          <div className="relative flex-1 max-w-sm">
            <SearchIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              placeholder="Search by title, message, type..."
              value={searchQuery}
              onChange={(e) => {
                const next = e.target.value
                startTransition(() => {
                  setSearchQuery(next)
                  setPage(0)
                })
              }}
              className="pl-8"
            />
          </div>
          <div className="flex items-center gap-2">
            <Select
              value={categoryFilter}
              onValueChange={handleFilterChange(setCategoryFilter)}
            >
              <SelectTrigger className="w-[160px] h-9">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All categories</SelectItem>
                {CATEGORY_ORDER.map((label) => (
                  <SelectItem key={label} value={label}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={severityFilter}
              onValueChange={handleFilterChange(setSeverityFilter)}
            >
              <SelectTrigger className="w-[150px] h-9">
                <SelectValue placeholder="Severity" />
              </SelectTrigger>
              <SelectContent>
                {SEVERITY_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={typeFilter}
              onValueChange={handleFilterChange(setTypeFilter)}
              disabled={categoryFilter !== 'all'}
            >
              <SelectTrigger className="w-[160px] h-9">
                <SelectValue placeholder="Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All types</SelectItem>
                {KNOWN_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={readFilter} onValueChange={handleFilterChange(setReadFilter)}>
              <SelectTrigger className="w-[140px] h-9">
                <SelectValue placeholder="Read state" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="unread">Unread</SelectItem>
                <SelectItem value="read">Read</SelectItem>
              </SelectContent>
            </Select>

            {hasFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearFilters}
                className="h-9 px-2 text-muted-foreground"
              >
                Clear
              </Button>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-border">
          {isPending && pageItems.length === 0 ? (
            // Inline filtering skeleton — keeps toolbar interactive.
            <div>
              {Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={`notif-filter-skel-${String(i)}`}
                  className="flex items-start gap-3 border-b px-4 py-3 last:border-b-0"
                >
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex items-center gap-2">
                      <Skeleton className="h-4 w-44" />
                      <Skeleton className="h-4 w-16 rounded-full" />
                    </div>
                    <Skeleton className="h-3 w-3/4 max-w-md" />
                    <div className="flex items-center gap-2">
                      <Skeleton className="h-3 w-20" />
                      <Skeleton className="h-3 w-28" />
                    </div>
                  </div>
                  <Skeleton className="h-7 w-7 rounded-md" />
                </div>
              ))}
            </div>
          ) : pageItems.length === 0 ? (
            <EmptyState
              icon={Inbox}
              title={hasFilters ? 'No notifications match your filters' : 'No notifications yet'}
              description={
                hasFilters
                  ? 'Loosen the category or severity filter, or clear them entirely.'
                  : "You'll see new alerts here as the system emits them."
              }
              action={
                hasFilters ? (
                  <Button variant="outline" size="sm" onClick={clearFilters}>
                    Clear filters
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <div>
              {pageItems.map((notification) => (
                <NotificationRow
                  key={notification.id}
                  notification={notification}
                  variant="expanded"
                  onMarkRead={handleMarkRead}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between px-2 py-4">
          <p className="text-sm text-muted-foreground">
            {totalFiltered === 0
              ? 'Showing 0 of 0 results'
              : `Showing ${pageStart + 1} to ${pageEnd} of ${totalFiltered} results`}
          </p>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon-sm"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={!hasPrevPage}
            >
              <ChevronLeftIcon />
              <span className="sr-only">Previous page</span>
            </Button>
            <Button
              variant="outline"
              size="icon-sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasNextPage}
            >
              <ChevronRightIcon />
              <span className="sr-only">Next page</span>
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
