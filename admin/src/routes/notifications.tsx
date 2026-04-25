import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, ChevronLeft, ChevronRight, Inbox, Loader2, Trash2 } from 'lucide-react'
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

  const queryParams = useMemo(
    () => ({
      unread_only: readFilter === 'unread',
      type: typeFilter !== 'all' ? typeFilter : undefined,
      severity: serverSeverity,
      skip: page * PAGE_SIZE,
      limit: PAGE_SIZE,
    }),
    [readFilter, typeFilter, serverSeverity, page],
  )

  const { data: notifications = [], isLoading, isFetching, refetch } = useQuery({
    queryKey: ['notifications', 'page', queryParams],
    queryFn: () => notificationsService.list(queryParams),
  })

  const filtered = useMemo(() => {
    if (selectedSeverities.size === ALL_SEVERITIES.length) {
      return notifications
    }
    return notifications.filter((n) =>
      selectedSeverities.has((n.severity ?? 'info') as NotificationSeverity),
    )
  }, [notifications, selectedSeverities])

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
    setPage(0)
  }

  const invalidateAll = async () => {
    await queryClient.invalidateQueries({ queryKey: ['notifications'] })
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
    readFilter !== 'all'

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
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <Bell className="h-5 w-5 text-muted-foreground" />
            Notifications
          </h1>
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
          <div className="flex h-64 flex-col items-center justify-center gap-2 text-center">
            <Inbox className="h-10 w-10 text-muted-foreground/50" />
            <p className="text-sm font-medium text-muted-foreground">
              {hasFilters ? 'No notifications match your filters' : 'No notifications yet'}
            </p>
            {hasFilters && (
              <Button variant="ghost" size="sm" onClick={resetFilters}>
                Clear filters
              </Button>
            )}
          </div>
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
  )
}
