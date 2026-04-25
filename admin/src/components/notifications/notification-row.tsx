import { Check, Trash2 } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { formatFullDatetime } from '@/lib/format-time'
import type { Notification } from '@/types'
import { SeverityBadge } from './severity-badge'

interface NotificationRowProps {
  notification: Notification
  variant?: 'compact' | 'expanded'
  onMarkRead?: (notification: Notification) => void
  onDelete?: (notification: Notification) => void
  className?: string
}

function relativeTime(value: string | null | undefined): string {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  try {
    return formatDistanceToNow(d, { addSuffix: true })
  } catch {
    return ''
  }
}

export function NotificationRow({
  notification,
  variant = 'compact',
  onMarkRead,
  onDelete,
  className,
}: NotificationRowProps) {
  const isUnread = !notification.read
  const isCritical = notification.severity === 'critical'
  const isExpanded = variant === 'expanded'

  return (
    <div
      className={cn(
        'border-b last:border-b-0 px-4 py-3 transition-colors',
        isUnread &&
          'bg-muted/50 border-l-2 border-l-primary/60',
        isCritical && isUnread && 'border-l-red-500',
        className,
      )}
    >
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p
              className={cn(
                'text-sm font-medium leading-tight',
                isExpanded && 'text-base',
              )}
            >
              {notification.title}
            </p>
            <SeverityBadge severity={notification.severity} />
            {isUnread && (
              <span className="inline-flex h-1.5 w-1.5 shrink-0 rounded-full bg-primary" aria-label="Unread" />
            )}
          </div>
          <p
            className={cn(
              'text-xs text-muted-foreground',
              isExpanded ? 'mt-1.5 line-clamp-none' : 'line-clamp-2',
            )}
          >
            {notification.message}
          </p>
          <div className="mt-1 flex items-center gap-2">
            <p
              className="font-mono text-[11px] tabular-nums text-muted-foreground/70"
              title={formatFullDatetime(notification.created_at)}
            >
              {relativeTime(notification.created_at) || formatFullDatetime(notification.created_at)}
            </p>
            {notification.type && (
              <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                {notification.type}
              </span>
            )}
          </div>
        </div>
        {isExpanded && (onMarkRead || onDelete) && (
          <div className="flex shrink-0 items-center gap-1">
            {onMarkRead && isUnread && (
              <Button
                type="button"
                size="icon-xs"
                variant="ghost"
                onClick={() => onMarkRead(notification)}
                title="Mark as read"
                aria-label="Mark as read"
              >
                <Check className="h-3 w-3" />
              </Button>
            )}
            {onDelete && (
              <Button
                type="button"
                size="icon-xs"
                variant="ghost"
                onClick={() => onDelete(notification)}
                title="Delete notification"
                aria-label="Delete notification"
                className="text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
