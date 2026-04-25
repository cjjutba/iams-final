import { Bell, Inbox } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { isToday, isYesterday } from 'date-fns'
import { useAuthStore } from '@/stores/auth.store'
import { useNotificationStore } from '@/stores/notification.store'
import { notificationsService } from '@/services/notifications.service'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Breadcrumbs } from './breadcrumbs'
import { NotificationRow } from '@/components/notifications/notification-row'
import type { Notification } from '@/types'

// Phase 8: bucket the popover's notifications into Today / Yesterday /
// Earlier so users can scan recent activity at a glance. Empty buckets
// are dropped so the popover stays compact.
type NotificationDateGroup = { label: string; items: Notification[] }

function groupNotificationsByDate(notifications: Notification[]): NotificationDateGroup[] {
  const groups: NotificationDateGroup[] = [
    { label: 'Today', items: [] },
    { label: 'Yesterday', items: [] },
    { label: 'Earlier', items: [] },
  ]
  for (const n of notifications) {
    const d = new Date(n.created_at)
    if (isToday(d)) groups[0].items.push(n)
    else if (isYesterday(d)) groups[1].items.push(n)
    else groups[2].items.push(n)
  }
  return groups.filter((g) => g.items.length > 0)
}

export function Header() {
  const { user, logout } = useAuthStore()
  const { unreadCount, unreadCriticalCount, fetchUnreadCount } = useNotificationStore()
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [notifOpen, setNotifOpen] = useState(false)
  const [loadingNotifs, setLoadingNotifs] = useState(false)

  const initials = user
    ? `${user.first_name.charAt(0)}${user.last_name.charAt(0)}`
    : 'AD'

  useEffect(() => {
    if (notifOpen) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setLoadingNotifs(true)
      notificationsService
        .list({ limit: 5 })
        .then((data) => setNotifications(data.slice(0, 5)))
        .catch(() => setNotifications([]))
        .finally(() => setLoadingNotifs(false))
    }
  }, [notifOpen])

  const handleMarkAllRead = async () => {
    try {
      await notificationsService.markAllRead()
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
      await fetchUnreadCount()
      toast.success('All notifications marked as read')
    } catch {
      toast.error('Failed to mark notifications as read')
    }
  }

  const handleLogout = () => {
    logout()
    toast.success('Signed out successfully')
  }

  const hasCriticalUnread = unreadCriticalCount > 0

  return (
    <header className="flex h-14 items-center gap-2 px-4">
      <SidebarTrigger className="-ml-1" />
      <Breadcrumbs />
      <div className="ml-auto flex items-center gap-1">
        <Popover open={notifOpen} onOpenChange={setNotifOpen}>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="h-4 w-4" />
              {unreadCount > 0 && (
                <Badge
                  variant="destructive"
                  className={`absolute -top-1 -right-1 h-4 min-w-4 px-1 text-[10px] leading-none ${
                    hasCriticalUnread ? 'animate-pulse bg-red-600 ring-2 ring-red-400/60' : ''
                  }`}
                >
                  {unreadCount > 99 ? '99+' : unreadCount}
                </Badge>
              )}
              {hasCriticalUnread && (
                <span
                  aria-label={`${unreadCriticalCount} critical alert${unreadCriticalCount === 1 ? '' : 's'}`}
                  className="pointer-events-none absolute -bottom-0.5 -right-0.5 inline-flex h-2 w-2 rounded-full bg-red-500 ring-2 ring-background"
                >
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-500 opacity-75" />
                </span>
              )}
              <span className="sr-only">Notifications</span>
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-96 p-0">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Notifications</span>
                {hasCriticalUnread && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-red-700 ring-1 ring-inset ring-red-200 dark:bg-red-950/40 dark:text-red-300 dark:ring-red-900">
                    <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-red-500" />
                    {unreadCriticalCount} critical
                  </span>
                )}
              </div>
              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={handleMarkAllRead}
                  className="text-xs text-muted-foreground hover:text-foreground cursor-pointer"
                >
                  Mark all read
                </button>
              )}
            </div>
            <div className="max-h-72 overflow-y-auto">
              {loadingNotifs ? (
                <div className="px-4 py-6 text-center text-sm text-muted-foreground">
                  Loading...
                </div>
              ) : notifications.length === 0 ? (
                <div className="flex flex-col items-center gap-2 px-4 py-6 text-center">
                  <Inbox className="h-8 w-8 text-muted-foreground/50" />
                  <span className="text-sm text-muted-foreground">No notifications</span>
                </div>
              ) : (
                groupNotificationsByDate(notifications.slice(0, 5)).map((group) => (
                  <div key={group.label}>
                    <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground bg-muted/40">
                      {group.label}
                    </div>
                    {group.items.map((notif) => (
                      <NotificationRow key={notif.id} notification={notif} variant="compact" />
                    ))}
                  </div>
                ))
              )}
            </div>
            <div className="border-t px-4 py-2 text-center">
              <Link
                to="/notifications"
                onClick={() => setNotifOpen(false)}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                View all notifications &rarr;
              </Link>
            </div>
          </PopoverContent>
        </Popover>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="relative h-8 w-8 rounded-full">
              <Avatar className="h-8 w-8">
                <AvatarFallback className="text-xs">{initials}</AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col gap-0.5">
                <p className="text-sm font-medium">
                  {user ? `${user.first_name} ${user.last_name}` : 'Admin'}
                </p>
                {user?.email && (
                  <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                )}
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout} className="cursor-pointer">
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
