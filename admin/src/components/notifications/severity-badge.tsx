import { cn } from '@/lib/utils'
import type { NotificationSeverity } from '@/types'

const STYLES: Record<NotificationSeverity, string> = {
  info: 'bg-blue-100 text-blue-700 ring-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:ring-blue-900',
  success:
    'bg-emerald-100 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-900',
  warn: 'bg-amber-100 text-amber-700 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-900',
  error:
    'bg-red-100 text-red-700 ring-red-200 dark:bg-red-950/40 dark:text-red-300 dark:ring-red-900',
  critical:
    'bg-red-200 text-red-900 ring-red-300 animate-pulse dark:bg-red-900/50 dark:text-red-200 dark:ring-red-800',
}

const LABELS: Record<NotificationSeverity, string> = {
  info: 'Info',
  success: 'Success',
  warn: 'Warning',
  error: 'Error',
  critical: 'Critical',
}

interface SeverityBadgeProps {
  severity: NotificationSeverity | undefined | null
  className?: string
}

export function SeverityBadge({ severity, className }: SeverityBadgeProps) {
  const sev: NotificationSeverity = severity ?? 'info'
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ring-1 ring-inset',
        STYLES[sev] ?? STYLES.info,
        className,
      )}
    >
      {LABELS[sev] ?? LABELS.info}
    </span>
  )
}
