/**
 * Shared status pill components.
 *
 * Single source of truth for the "what state is this thing in" UI vocabulary
 * used across the admin portal. Before this module existed, every list and
 * detail page had its own slightly-different rendering of the same booleans
 * — `<Badge variant="default">Active</Badge>` here, an inline-flex with a
 * green check icon there, a tinted span somewhere else. The result was that
 * an operator scanning the Schedules list and the Schedule detail saw three
 * different "Active" treatments.
 *
 * The redesign cadence settled on:
 *   - rounded-full border + tinted bg + colored text (light + dark mode)
 *   - small pulse dot for "live" / "now" states
 *   - emerald for success/active, amber for warning, red for destructive,
 *     blue for informational, muted for neutral
 *
 * All pills are plain `<span>`s so they drop into table cells without the
 * `<Badge>` component's hover styles fighting with `<TableRow>` hover.
 */

import { Check, ScanLine, X } from 'lucide-react'
import type { ScheduleRuntimeStatus, AttendanceStatus } from '@/types'
import { formatStatus } from '@/types/attendance'

// ---------------------------------------------------------------------------
// Internal building blocks
// ---------------------------------------------------------------------------

const BASE =
  'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide whitespace-nowrap'

const TONE = {
  emerald:
    'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
  amber:
    'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400',
  orange:
    'border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-400',
  red: 'border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400',
  blue: 'border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-400',
  muted: 'border-muted-foreground/30 text-muted-foreground',
} as const

type Tone = keyof typeof TONE

function PulseDot({ tone }: { tone: 'emerald' | 'amber' | 'red' }) {
  const dot =
    tone === 'emerald'
      ? 'bg-emerald-500'
      : tone === 'amber'
        ? 'bg-amber-500'
        : 'bg-red-500'
  return (
    <span className="relative mr-0.5 flex h-1.5 w-1.5" aria-hidden>
      <span
        className={`absolute inline-flex h-full w-full animate-ping rounded-full ${dot} opacity-75`}
      />
      <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${dot}`} />
    </span>
  )
}

function StaticDot({ tone }: { tone: Tone }) {
  const dot =
    tone === 'emerald'
      ? 'bg-emerald-500'
      : tone === 'amber'
        ? 'bg-amber-500'
        : tone === 'orange'
          ? 'bg-orange-500'
          : tone === 'red'
            ? 'bg-red-500'
            : tone === 'blue'
              ? 'bg-blue-500'
              : 'bg-muted-foreground/60'
  return <span className={`mr-0.5 inline-block h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden />
}

// ---------------------------------------------------------------------------
// Concrete pills
// ---------------------------------------------------------------------------

/** Generic enable/archive flag — used everywhere `is_active` is shown. */
export function ActiveStatusPill({ active }: { active: boolean }) {
  return active ? (
    <span className={`${BASE} ${TONE.emerald}`}>Active</span>
  ) : (
    <span className={`${BASE} ${TONE.muted}`}>Inactive</span>
  )
}

/** `email_verified` boolean → tinted Verified / Not verified pill. */
export function EmailVerifiedPill({ verified }: { verified: boolean }) {
  return verified ? (
    <span className={`${BASE} ${TONE.emerald}`}>
      <Check className="h-3 w-3" aria-hidden />
      Verified
    </span>
  ) : (
    <span className={`${BASE} ${TONE.amber}`}>
      <X className="h-3 w-3" aria-hidden />
      Not verified
    </span>
  )
}

/** `is_registered` (student app account linked) → tinted pill. */
export function AppLinkedPill({ linked }: { linked: boolean }) {
  return linked ? (
    <span className={`${BASE} ${TONE.blue}`}>App linked</span>
  ) : (
    <span className={`${BASE} ${TONE.muted}`}>Not linked</span>
  )
}

/**
 * `has_face_registered` → tinted pill.
 * `applicable=false` is rendered as an em-dash for rows where face
 * registration is conceptually N/A (e.g. a student record without an app
 * account yet).
 */
export function FaceStatusPill({
  registered,
  applicable = true,
}: {
  registered: boolean
  applicable?: boolean
}) {
  if (!applicable) {
    return <span className="text-sm text-muted-foreground">—</span>
  }
  return registered ? (
    <span className={`${BASE} ${TONE.emerald}`}>
      <ScanLine className="h-3 w-3" aria-hidden />
      Enrolled
    </span>
  ) : (
    <span className={`${BASE} ${TONE.amber}`}>Pending</span>
  )
}

const RUNTIME_STATUS_META: Record<
  ScheduleRuntimeStatus,
  { label: string; tone: Tone; pulse: boolean }
> = {
  live: { label: 'Live', tone: 'emerald', pulse: true },
  upcoming: { label: 'Upcoming', tone: 'amber', pulse: false },
  ended: { label: 'Ended today', tone: 'muted', pulse: false },
  scheduled: { label: 'Scheduled', tone: 'muted', pulse: false },
  disabled: { label: 'Disabled', tone: 'muted', pulse: false },
}

/** Schedule runtime state — Live pulses, others are static dots. */
export function RuntimeStatusPill({ status }: { status: ScheduleRuntimeStatus }) {
  const meta = RUNTIME_STATUS_META[status] ?? RUNTIME_STATUS_META.scheduled
  return (
    <span className={`${BASE} ${TONE[meta.tone]}`}>
      {meta.pulse && meta.tone === 'emerald' ? (
        <PulseDot tone="emerald" />
      ) : (
        <StaticDot tone={meta.tone} />
      )}
      {meta.label}
    </span>
  )
}

const ATTENDANCE_TONE: Record<AttendanceStatus, Tone> = {
  present: 'emerald',
  late: 'amber',
  early_leave: 'orange',
  absent: 'red',
  excused: 'blue',
}

/** Attendance record status — color-coded by status enum. */
export function AttendanceStatusPill({ status }: { status: AttendanceStatus }) {
  const tone = ATTENDANCE_TONE[status] ?? 'muted'
  return (
    <span className={`${BASE} ${TONE[tone]}`}>{formatStatus(status)}</span>
  )
}

/**
 * Pulsing "Live now" pill — used in the rooms list when any schedule for
 * the room is currently in its live window, or anywhere we want to call
 * attention to an in-progress session.
 */
export function LiveNowPill() {
  return (
    <span className={`${BASE} ${TONE.emerald}`}>
      <PulseDot tone="emerald" />
      Live now
    </span>
  )
}

/**
 * Generic camera presence indicator — used in the rooms list where the
 * column historically rendered the raw RTSP URL. Hides infrastructure plumbing
 * behind a simple boolean while still letting operators see at a glance which
 * rooms have an endpoint configured.
 */
export function CameraConfiguredPill({ configured }: { configured: boolean }) {
  return configured ? (
    <span className={`${BASE} ${TONE.emerald}`}>Configured</span>
  ) : (
    <span className={`${BASE} ${TONE.muted}`}>Not configured</span>
  )
}
