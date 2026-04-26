import { useState } from 'react'
import { ChevronDown, Info } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type {
  RecognitionDecisionReason,
  TrackInfo,
} from '@/hooks/use-attendance-ws'

interface Props {
  track: TrackInfo | null
}

// Operator-facing rationale for every decision_reason value the backend
// can emit. The map is the single source of truth for the panel — when
// a new reason is added server-side, add it here and the UI just works.
const REASON_COPY: Record<
  RecognitionDecisionReason,
  { label: string; tone: 'ok' | 'warn' | 'fail' | 'pending'; help: string }
> = {
  matched: {
    label: 'Matched',
    tone: 'ok',
    help: 'FAISS top-1 cleared the threshold and the swap-gate / frame-mutex did not patch the result. Track is recognized.',
  },
  below_threshold: {
    label: 'Below threshold',
    tone: 'fail',
    help: 'The closest match was below the cosine-similarity floor. Likely cause: pose / occlusion / lighting at this frame produced a low-quality embedding.',
  },
  below_phone_only_threshold: {
    label: 'Below phone-only threshold',
    tone: 'fail',
    help: 'This user has zero CCTV embeddings for this room, so a stricter cutoff applies (RECOGNITION_THRESHOLD + PHONE_ONLY_BONUS). Run scripts.cctv_enroll or wait for auto-enrol to capture some.',
  },
  ambiguous_margin: {
    label: 'Margin gate',
    tone: 'warn',
    help: 'Top-1 and top-2 candidates were too close together. The matcher refuses to commit until one stands clearly above the other (RECOGNITION_MARGIN).',
  },
  swap_blocked: {
    label: 'Swap blocked',
    tone: 'warn',
    help: 'A different user is currently scoring higher than the incumbent, but the vote-streak gate (RECOGNITION_SWAP_MIN_STREAK) has not yet been satisfied. The incumbent is held until the candidate sustains for more frames.',
  },
  mutex_demoted: {
    label: 'Mutex demoted',
    tone: 'warn',
    help: 'Another track in the same frame had a higher confidence on the same user_id. The Hungarian frame-mutex routed this track to its top-2 fallback (or cleared its binding).',
  },
  no_faiss_hit: {
    label: 'No FAISS hit',
    tone: 'fail',
    help: 'FAISS returned nothing close enough to be the top-1. Either the index has no near-matching embeddings, or the live face is too unlike anything registered.',
  },
  orphaned_user_id: {
    label: 'Orphaned user',
    tone: 'fail',
    help: 'FAISS top-1 named a user_id that is no longer in the database. Stale embedding — run scripts.rebuild_faiss to clean up.',
  },
  kps_implausible: {
    label: 'Landmarks implausible',
    tone: 'warn',
    help: 'SCRFD emitted keypoints that failed the topology check (eyes above nose above mouth, plausible eye spacing). Common when a hand or hair partially occludes the face.',
  },
  quality_gated: {
    label: 'Quality gate',
    tone: 'warn',
    help: 'The face crop was too blurry, too dark, or too small to produce a reliable embedding. Skipped this frame and will retry on the next clean detection.',
  },
  reverify_not_due: {
    label: 'Re-verify not due',
    tone: 'pending',
    help: 'Track is recognized and within its REVERIFY_INTERVAL window. Showing the most recent FAISS decision; nothing was searched this frame.',
  },
  no_embedding_budget: {
    label: 'Embed budget capped',
    tone: 'pending',
    help: 'Per-frame re-verify budget (MAX_REVERIFIES_PER_FRAME) was exhausted by other tracks. Will be searched on a subsequent frame.',
  },
  warming_up: {
    label: 'Warming up',
    tone: 'pending',
    help: 'Track has not yet committed to recognized OR unknown. Within the UNKNOWN_CONFIRM_ATTEMPTS window — needs a few more frames of evidence either way.',
  },
  no_search_this_frame: {
    label: 'Not searched',
    tone: 'pending',
    help: 'Track was not picked for FAISS this frame. No diagnostic information available yet — wait for the next re-verify cadence.',
  },
}

const FALLBACK_REASON: (typeof REASON_COPY)[RecognitionDecisionReason] = {
  label: 'Unknown reason',
  tone: 'pending',
  help: 'Backend reported a decision_reason this client does not recognize. Check the server logs.',
}

function reasonStyle(tone: 'ok' | 'warn' | 'fail' | 'pending'): {
  badge: string
  dot: string
} {
  switch (tone) {
    case 'ok':
      return {
        badge:
          'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30',
        dot: 'bg-emerald-500',
      }
    case 'warn':
      return {
        badge:
          'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30',
        dot: 'bg-amber-500',
      }
    case 'fail':
      return {
        badge:
          'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/30',
        dot: 'bg-red-500',
      }
    case 'pending':
    default:
      return {
        badge:
          'bg-sky-500/10 text-sky-700 dark:text-sky-400 border-sky-500/30',
        dot: 'bg-sky-500',
      }
  }
}

interface ScoreRowProps {
  label: string
  userId: string | null | undefined
  name: string | null | undefined
  score: number | undefined
  threshold: number
  isMatch: boolean
}

function ScoreRow({
  label,
  userId,
  name,
  score,
  threshold,
  isMatch,
}: ScoreRowProps) {
  const hasScore = typeof score === 'number' && score > 0
  const pct = hasScore ? Math.max(0, Math.min(100, score * 100)) : 0
  const aboveThreshold = hasScore && score >= threshold
  const labelClass = isMatch
    ? 'text-emerald-700 dark:text-emerald-400'
    : 'text-muted-foreground'
  const barClass = !hasScore
    ? 'bg-muted-foreground/20'
    : aboveThreshold
      ? 'bg-emerald-500'
      : 'bg-amber-500'
  const numClass = !hasScore
    ? 'text-muted-foreground/50'
    : aboveThreshold
      ? 'text-emerald-600 dark:text-emerald-400'
      : 'text-amber-600 dark:text-amber-500'

  return (
    <div className="flex items-center gap-3">
      <div className="flex w-14 shrink-0 flex-col">
        <span
          className={`text-[10px] font-semibold uppercase tracking-[0.08em] ${labelClass}`}
        >
          {label}
        </span>
        {isMatch && (
          <span className="text-[9.5px] text-emerald-600 dark:text-emerald-400">
            committed
          </span>
        )}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex items-baseline justify-between gap-3">
          <span className="truncate text-[12px] font-medium">
            {name || (
              <span className="italic text-muted-foreground">
                {hasScore ? 'unresolved name' : '—'}
              </span>
            )}
          </span>
          <span
            className={`shrink-0 font-mono text-[12px] tabular-nums ${numClass}`}
          >
            {hasScore ? score!.toFixed(3) : '—'}
          </span>
        </div>
        <div className="relative h-1 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={`h-full rounded-full transition-all duration-300 ${barClass}`}
            style={{ width: `${pct}%` }}
          />
          <div
            className="pointer-events-none absolute top-0 h-full w-px bg-foreground/40"
            style={{ left: `${threshold * 100}%` }}
            aria-hidden
          />
        </div>
        {userId && (
          <span className="truncate font-mono text-[10px] text-muted-foreground/70">
            {userId.slice(0, 16)}
          </span>
        )}
      </div>
    </div>
  )
}

/**
 * Surfaces the per-track recognition diagnostics from the backend so the
 * operator can see top-1 / top-2 / decision_reason / effective threshold
 * directly in the Track Detail Sheet — no more grepping dozzle to answer
 * "why is this face Unknown?".
 *
 * Renders as a collapsible block under the SimilarityMetrics card. Stays
 * collapsed by default so the regular comparison view isn't cluttered for
 * happy-path recognitions; expands on click for any track the operator
 * actually wants to debug.
 */
export function RecognitionDiagnostics({ track }: Props) {
  const [expanded, setExpanded] = useState(true)

  if (!track) return null

  // Backend may not emit these fields on older builds. Provide sensible
  // defaults so the UI doesn't render NaN or undefined string literals.
  const reason = (track.decision_reason ??
    'no_search_this_frame') as RecognitionDecisionReason
  const reasonInfo = REASON_COPY[reason] ?? FALLBACK_REASON
  const reasonStyles = reasonStyle(reasonInfo.tone)

  const top1Score = track.top1_score ?? 0
  const top2Score = track.top2_score ?? 0
  const threshold = track.effective_threshold ?? 0
  const bestSeen = track.best_score_seen ?? 0
  const unknownAttempts = track.unknown_attempts ?? 0
  const framesSeen = track.frames_seen ?? 0
  const searched = track.decision_searched ?? false

  // Top-1 user_id matching the bound user → the committed identity is
  // the FAISS top-1 (happy path). Top-2 user_id matching the bound user
  // → the frame-mutex demoted top-1 to top-2 fallback.
  const top1IsCommitted = !!(
    track.user_id && track.top1_user_id === track.user_id
  )
  const top2IsCommitted = !!(
    track.user_id && track.top2_user_id === track.user_id
  )

  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-card/30 p-4">
      {/* Header with reason badge + toggle */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="text-[10.5px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
            Recognition Decision
          </span>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span
                  className="inline-flex h-3.5 w-3.5 items-center justify-center text-muted-foreground/60"
                  aria-label="Why is this face Unknown?"
                >
                  <Info className="h-3 w-3" />
                </span>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-xs text-[11px]">
                {reasonInfo.help}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <div className="flex items-center gap-1.5">
          <Badge
            variant="outline"
            className={`shrink-0 gap-1.5 px-2 py-0.5 text-[11px] font-medium ${reasonStyles.badge}`}
          >
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${reasonStyles.dot}`}
              aria-hidden
            />
            {reasonInfo.label}
          </Badge>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => setExpanded((v) => !v)}
            aria-label={expanded ? 'Collapse diagnostics' : 'Expand diagnostics'}
          >
            <ChevronDown
              className={`h-3.5 w-3.5 transition-transform ${expanded ? 'rotate-180' : ''}`}
            />
          </Button>
        </div>
      </div>

      {expanded && (
        <>
          {/* Help text */}
          <p className="text-[11px] leading-snug text-muted-foreground">
            {reasonInfo.help}
          </p>

          {/* Top-1 / Top-2 comparison */}
          <div className="flex flex-col gap-3 border-t border-border/60 pt-3">
            <ScoreRow
              label="Top 1"
              userId={track.top1_user_id ?? null}
              name={track.top1_name ?? null}
              score={top1Score}
              threshold={threshold}
              isMatch={top1IsCommitted}
            />
            <ScoreRow
              label="Top 2"
              userId={track.top2_user_id ?? null}
              name={track.top2_name ?? null}
              score={top2Score}
              threshold={threshold}
              isMatch={top2IsCommitted}
            />
          </div>

          {/* Footer stats grid */}
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 border-t border-border/60 pt-3 text-[11px]">
            <Stat
              label="Effective threshold"
              value={threshold > 0 ? threshold.toFixed(3) : '—'}
              hint={
                track.top1_user_id && threshold > 0
                  ? threshold > 0.5
                    ? 'Phone-only bonus active — register CCTV captures to drop to baseline.'
                    : 'Standard threshold (CCTV-enrolled).'
                  : undefined
              }
            />
            <Stat
              label="Best seen"
              value={bestSeen > 0 ? bestSeen.toFixed(3) : '—'}
              hint={
                bestSeen >= threshold && !top1IsCommitted
                  ? 'This track previously matched. Likely transient pose/blur recovery.'
                  : undefined
              }
            />
            <Stat
              label="Unknown misses"
              value={unknownAttempts > 0 ? `${unknownAttempts}` : '—'}
              hint={
                unknownAttempts > 0
                  ? 'Will commit to "Unknown" once UNKNOWN_CONFIRM_ATTEMPTS is reached (default 5).'
                  : undefined
              }
            />
            <Stat
              label="Frames tracked"
              value={`${framesSeen}`}
              hint={
                framesSeen < 5
                  ? 'Brand-new track. Warming up is expected during the first few frames.'
                  : undefined
              }
            />
          </div>

          {/* Flag chips */}
          {(track.swap_blocked || track.mutex_demoted || !searched) && (
            <div className="flex flex-wrap gap-1.5 border-t border-border/60 pt-3">
              {track.swap_blocked && (
                <Badge
                  variant="outline"
                  className="gap-1 px-2 py-0.5 text-[10px] font-medium bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30"
                >
                  Swap held
                </Badge>
              )}
              {track.mutex_demoted && (
                <Badge
                  variant="outline"
                  className="gap-1 px-2 py-0.5 text-[10px] font-medium bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30"
                >
                  Mutex demoted
                </Badge>
              )}
              {!searched && (
                <Badge
                  variant="outline"
                  className="gap-1 px-2 py-0.5 text-[10px] font-medium bg-muted text-muted-foreground border-border"
                >
                  Cached (not searched this frame)
                </Badge>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

interface StatProps {
  label: string
  value: string
  hint?: string
}

function Stat({ label, value, hint }: StatProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <span className="font-mono tabular-nums text-foreground/90">
          {value}
        </span>
      </div>
      {hint && (
        <span className="text-[10px] leading-tight text-muted-foreground/70">
          {hint}
        </span>
      )}
    </div>
  )
}
