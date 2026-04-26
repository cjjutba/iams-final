import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Inbox, Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { usePageTitle } from '@/hooks/use-page-title'
import { Button } from '@/components/ui/button'
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
import { cn } from '@/lib/utils'
import { notificationsService } from '@/services/notifications.service'
import { useNotificationStore } from '@/stores/notification.store'
import { NotificationRow } from '@/components/notifications/notification-row'
import { EmptyState } from '@/components/shared/empty-state'
import type { Notification, NotificationSeverity } from '@/types'

const ALL_SEVERITIES: NotificationSeverity[] = [
  'info',
  'success',
  'warn',
  'error',
  'critical',
]

const SEVERITY_LABELS: Record<NotificationSeverity, string> = {
  info: 'Info',
  success: 'Success',
  warn: 'Warning',
  error: 'Error',
  critical: 'Critical',
}

// Known notification types as of Phase 2. Future event sources should be
// added here so they're available in the type filter dropdown. Backend
// remains the source of truth — anything it sends that's not in this
// list still appears in the rendered list, just not as a filter option.
const KNOWN_TYPES = [
  'check_in',
  'early_leave',
  'early_leave_return',
  'session_start',
  'session_end',
  'low_attendance_warning',
  'anomaly_alert',
  'daily_digest',
  'weekly_digest',
  'broadcast',
  'system',
] as const

// Phase 8: type-grouped sidebar buckets. The category labels are admin
// UX, not a backend contract — types not in any bucket fall through and
// stay reachable via the legacy "All types" dropdown. Keep aligned with
// the ~30 notification_type tags emitted by notification_service.py.
const NOTIFICATION_CATEGORIES: Record<string, string[]> = {
  'Operational Health': [
    'camera_offline',
    'camera_recovered',
    'rtsp_connection_failed',
    'frame_stale',
    'ml_sidecar_down',
    'ml_sidecar_recovered',
    'faiss_mismatch',
    'faiss_reconcile_failed',
    'redis_connection_lost',
  ],
  'Security & Recognition': [
    'unknown_person_detected',
    'face_registration_pending_review',
    'face_registration_approved',
    'face_registration_rejected',
    'face_re_registration_required',
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
    'schedule_assigned',
    'schedule_updated',
    'schedule_deleted',
    'schedule_conflict_warning',
    'enrollment_added',
    'enrollment_removed',
  ],
  'System': [
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

type ReadFilter = 'all' | 'unread'

const PAGE_SIZE = 50

export default function NotificationsPage() {
  usePageTitle('Notifications')
  const queryClient = useQueryClient()
  const { fetchUnreadCount } = useNotificationStore()

  const [selectedSeverities, setSelectedSeverities] = useState<Set<NotificationSeverity>>(
    () => new Set(ALL_SEVERITIES),
  )
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [readFilter, setReadFilter] = useState<ReadFilter>('all')
  // Phase 8: active sidebar category. When non-null, the request still
  // fetches unfiltered (server only supports a single `type`) but the
  // client-side filter narrows to the category's type list.
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [page, setPage] = useState(0)

  // We always fetch a single severity-or-all batch from the server and
  // narrow client-side. The backend supports a single `severity` param
  // (Phase 1), so for the multi-select case we fall back to fetching
  // unfiltered + filtering in memory. This keeps the wire contract
  // honest and avoids issuing N parallel requests.
  const serverSeverity =
    selectedSeverities.size === 1
      ? Array.from(selectedSeverities)[0]
      : undefined

  // When a category is active, the type dropdown is overridden — the
  // backend only accepts a single `type` value, so we fetch unfiltered
  // and narrow client-side to the category's full type list.
  const serverTypeFilter = activeCategory
    ? undefined
    : typeFilter !== 'all'
      ? typeFilter
      : undefined

  const queryParams = useMemo(
    () => ({
      unread_only: readFilter === 'unread',
      type: serverTypeFilter,
      severity: serverSeverity,
      skip: page * PAGE_SIZE,
      limit: PAGE_SIZE,
    }),
    [readFilter, serverTypeFilter, serverSeverity, page],
  )

  const { data: notifications = [], isLoading, isFetching, refetch } = useQuery({
    queryKey: ['notifications', 'page', queryParams],
    queryFn: () => notificationsService.list(queryParams),
  })

  // Phase 8: per-category unread counts for the sidebar. Invalidated
  // alongside ['notifications'] whenever a row is mutated (mark-read,
  // delete, mark-all-read, clear-all) so the badges stay in sync.
  const { data: stats } = useQuery({
    queryKey: ['notification-stats'],
    queryFn: () => notificationsService.stats(),
  })

  const categoryUnreadCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    const byType = stats?.by_type ?? {}
    for (const [label, types] of Object.entries(NOTIFICATION_CATEGORIES)) {
      let n = 0
      for (const t of types) n += byType[t] ?? 0
      counts[label] = n
    }
    return counts
  }, [stats])

  const totalUnread = stats?.total ?? 0

  const filtered = useMemo(() => {
    let result = notifications
    // Apply category narrowing (client-side) when active.
    if (activeCategory) {
      const allowed = new Set(NOTIFICATION_CATEGORIES[activeCategory] ?? [])
      result = result.filter((n) => allowed.has(n.type))
    }
    if (selectedSeverities.size !== ALL_SEVERITIES.length) {
      result = result.filter((n) =>
        selectedSeverities.has((n.severity ?? 'info') as NotificationSeverity),
      )
    }
    return result
  }, [notifications, selectedSeverities, activeCategory])

  const toggleSeverity = (sev: NotificationSeverity) => {
    setPage(0)
    setSelectedSeverities((prev) => {
      const next = new Set(prev)
      if (next.has(sev)) next.delete(sev)
      else next.add(sev)
      // Don't allow zero-selected — reset to all instead.
      if (next.size === 0) return new Set(ALL_SEVERITIES)
      return next
    })
  }

  const resetFilters = () => {
    setSelectedSeverities(new Set(ALL_SEVERITIES))
    setTypeFilter('all')
    setReadFilter('all')
    setActiveCategory(null)
    setPage(0)
  }

  const selectCategory = (category: string | null) => {
    setActiveCategory(category)
    // Picking a category overrides the legacy single-type dropdown so
    // the two filters can't fight each other.
    if (category !== null) setTypeFilter('all')
    setPage(0)
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

  const hasFilters =
    selectedSeverities.size !== ALL_SEVERITIES.length ||
    typeFilter !== 'all' ||
    readFilter !== 'all' ||
    activeCategory !== null

  // Server returns up to PAGE_SIZE items. If we got a full page, assume
  // there might be more. The backend doesn't currently return a total
  // count, so we use a "next-if-full" heuristic — same as the existing
  // recognitions page.
  const hasNextPage = notifications.length >= PAGE_SIZE
  const hasPrevPage = page > 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Notifications</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            All system notifications and alerts.
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

      <div className="grid gap-6 md:grid-cols-[220px_1fr]">
        <aside className="space-y-1">
          <div className="px-2 pb-2 text-xs uppercase tracking-wide text-muted-foreground">
            Categories
          </div>
          <button
            type="button"
            onClick={() => selectCategory(null)}
            className={cn(
              'flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors',
              activeCategory === null
                ? 'bg-primary/10 font-medium text-foreground ring-1 ring-inset ring-primary/30'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
          >
            <span>All</span>
            {totalUnread > 0 && (
              <span
                className={cn(
                  'inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-medium',
                  activeCategory === null
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground',
                )}
              >
                {totalUnread > 99 ? '99+' : totalUnread}
              </span>
            )}
          </button>
          {CATEGORY_ORDER.map((label) => {
            const active = activeCategory === label
            const count = categoryUnreadCounts[label] ?? 0
            return (
              <button
                key={label}
                type="button"
                onClick={() => selectCategory(label)}
                className={cn(
                  'flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors',
                  active
                    ? 'bg-primary/10 font-medium text-foreground ring-1 ring-inset ring-primary/30'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                <span className="truncate">{label}</span>
                {count > 0 && (
                  <span
                    className={cn(
                      'inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-medium',
                      active
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground',
                    )}
                  >
                    {count > 99 ? '99+' : count}
                  </span>
                )}
              </button>
            )
          })}
        </aside>

        <div className="space-y-6">
          <div className="rounded-md border bg-muted/30 p-4">
            <div className="flex flex-wrap items-end gap-4">
              <div className="flex flex-col gap-1.5">
                <span className="text-xs uppercase tracking-wide text-muted-foreground">
                  Severity
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {ALL_SEVERITIES.map((sev) => {
                    const active = selectedSeverities.has(sev)
                    return (
                      <button
                        key={sev}
                        type="button"
                        onClick={() => toggleSeverity(sev)}
                        className={cn(
                          'rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition-colors',
                          active
                            ? 'bg-primary text-primary-foreground ring-primary'
                            : 'bg-background text-muted-foreground ring-border hover:bg-muted',
                        )}
                      >
                        {SEVERITY_LABELS[sev]}
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <span className="text-xs uppercase tracking-wide text-muted-foreground">
                  Type
                </span>
                <Select
                  value={typeFilter}
                  onValueChange={(v) => {
                    setTypeFilter(v)
                    setPage(0)
                  }}
                  disabled={activeCategory !== null}
                >
                  <SelectTrigger className="h-9 w-56">
                    <SelectValue />
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
              </div>

              <div className="flex flex-col gap-1.5">
                <span className="text-xs uppercase tracking-wide text-muted-foreground">
                  Read state
                </span>
                <Select
                  value={readFilter}
                  onValueChange={(v) => {
                    setReadFilter(v as ReadFilter)
                    setPage(0)
                  }}
                >
                  <SelectTrigger className="h-9 w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="unread">Unread only</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {hasFilters && (
                <Button variant="ghost" onClick={resetFilters} className="h-9">
                  Clear filters
                </Button>
              )}

              <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
                {isFetching && <Loader2 className="h-3 w-3 animate-spin" />}
                <span>
                  {filtered.length} {filtered.length === 1 ? 'notification' : 'notifications'} on
                  this page
                </span>
                <Button variant="outline" size="sm" onClick={() => refetch()} className="h-7">
                  Refresh
                </Button>
              </div>
            </div>
          </div>

          <div className="overflow-hidden rounded-md border">
            {isLoading ? (
              <div className="flex h-64 items-center justify-center text-muted-foreground">
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                <span className="text-sm">Loading notifications...</span>
              </div>
            ) : filtered.length === 0 ? (
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
                    <Button variant="outline" size="sm" onClick={resetFilters}>
                      Clear filters
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              <div>
                {filtered.map((notification) => (
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

          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              Page {page + 1}
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={!hasPrevPage || isFetching}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                <ChevronLeft className="mr-1 h-3.5 w-3.5" />
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={!hasNextPage || isFetching}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
                <ChevronRight className="ml-1 h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
