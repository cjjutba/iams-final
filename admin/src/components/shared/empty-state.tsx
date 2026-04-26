import type { LucideIcon } from 'lucide-react'

interface EmptyStateProps {
  /**
   * Icon component (typically a lucide-react icon). Rendered at neutral muted
   * weight inside a soft circular backdrop so the empty state has presence
   * without competing with surrounding chrome.
   */
  icon?: LucideIcon
  /** Short title — what's missing? "No early leaves yet". */
  title: string
  /**
   * Optional supporting copy — usually one short sentence explaining why the
   * state is empty (e.g. "Events appear when the pipeline detects a 3-scan
   * absence"). Skip when the title is self-explanatory.
   */
  description?: string
  /** Optional action — a button or link the operator can click to fix the void. */
  action?: React.ReactNode
  /**
   * Visual size — `compact` for inline empty states inside cards or table
   * bodies, `default` for full-width sections, `inline` for a single-line
   * "no results" inside a table.
   */
  size?: 'inline' | 'compact' | 'default'
}

/**
 * Standardized empty state. Replaces the scattered `<p>No results</p>` and
 * ad-hoc divs around the admin portal so every "nothing to show" surface
 * has the same vocabulary, spacing, and tone.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  size = 'default',
}: EmptyStateProps) {
  if (size === 'inline') {
    return (
      <div className="flex flex-col items-center justify-center gap-1 px-4 py-8 text-center">
        <p className="text-sm text-muted-foreground">{title}</p>
        {description && (
          <p className="text-xs text-muted-foreground/80">{description}</p>
        )}
      </div>
    )
  }

  const padding = size === 'compact' ? 'py-8' : 'py-16'

  return (
    <div className={`flex flex-col items-center justify-center px-6 ${padding} text-center`}>
      {Icon && (
        <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-muted">
          <Icon className="h-5 w-5 text-muted-foreground" aria-hidden />
        </div>
      )}
      <h3 className="text-sm font-medium text-foreground">{title}</h3>
      {description && (
        <p className="mt-1 max-w-sm text-xs text-muted-foreground">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
