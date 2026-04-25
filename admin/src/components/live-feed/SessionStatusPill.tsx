import type { SessionEligibility } from '@/services/presence.service'

interface SessionStatusPillProps {
  sessionActive: boolean | null
  eligibility: SessionEligibility | undefined
}

function formatClock(iso: string): string {
  return new Date(iso)
    .toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true })
    .replace(/^0/, '')
}

export function SessionStatusPill({ sessionActive, eligibility }: SessionStatusPillProps) {
  let label: string
  let dotClass: string
  let pulse = false

  if (sessionActive === true) {
    label = 'LIVE'
    dotClass = 'bg-emerald-500'
    pulse = true
  } else if (!eligibility) {
    label = 'IDLE'
    dotClass = 'bg-muted-foreground/60'
  } else {
    switch (eligibility.code) {
      case 'ALLOWED':
        label = 'READY'
        dotClass = 'bg-amber-500'
        break
      case 'TOO_EARLY':
        label = `STARTS ${formatClock(eligibility.available_at)}`
        dotClass = 'bg-muted-foreground/60'
        break
      case 'AFTER_END':
        label = 'ENDED'
        dotClass = 'bg-muted-foreground/60'
        break
      case 'ALREADY_RAN_TODAY':
        label = 'COMPLETED'
        dotClass = 'bg-muted-foreground/60'
        break
      case 'RUNNING':
        label = 'LIVE'
        dotClass = 'bg-emerald-500'
        pulse = true
        break
      default:
        label = 'IDLE'
        dotClass = 'bg-muted-foreground/60'
    }
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border bg-card px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide text-foreground">
      <span className="relative flex h-1.5 w-1.5">
        {pulse && (
          <span
            className={`absolute inline-flex h-full w-full animate-ping rounded-full ${dotClass} opacity-75`}
          />
        )}
        <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${dotClass}`} />
      </span>
      {label}
    </span>
  )
}
