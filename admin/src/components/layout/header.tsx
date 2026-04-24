import { Bell, Inbox } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
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
import type { Notification } from '@/types'

export function Header() {
  const { user, logout } = useAuthStore()
  const { unreadCount, fetchUnreadCount } = useNotificationStore()
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
        .list()
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
                  className="absolute -top-1 -right-1 h-4 min-w-4 px-1 text-[10px] leading-none"
                >
                  {unreadCount > 99 ? '99+' : unreadCount}
                </Badge>
              )}
              <span className="sr-only">Notifications</span>
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-80 p-0">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <span className="text-sm font-medium">Notifications</span>
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
                notifications.map((notif) => (
                  <div
                    key={notif.id}
                    className={`border-b last:border-b-0 px-4 py-3 ${!notif.read ? 'bg-muted/50' : ''}`}
                  >
                    <p className="text-sm font-medium">{notif.title}</p>
                    <p className="text-xs text-muted-foreground line-clamp-2">{notif.message}</p>
                    <p className="mt-1 text-[11px] text-muted-foreground/70">
                      {new Date(notif.created_at).toLocaleDateString()}
                    </p>
                  </div>
                ))
              )}
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
