import { useEffect, useState } from 'react'
import { Loader2, Save, Timer } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import { useUpdateScheduleConfig } from '@/hooks/use-queries'

const MIN_MINUTES = 1
const MAX_MINUTES = 15
// Mirror of backend's `EARLY_LEAVE_TIMEOUT` (300s = 5min). When the
// schedule's `early_leave_timeout_minutes` is null, this is the value
// the running pipeline actually uses, so it's the value we show as the
// slider's starting position too.
const DEFAULT_MINUTES = 5

interface Props {
  scheduleId: string
  /** Current persisted value from the schedule row; null = system default. */
  currentMinutes: number | null
  /** When true, render without the surrounding panel (for popover use). */
  inline?: boolean
  /** Emitted after a successful save so parents can close popovers. */
  onSaved?: () => void
  /**
   * Free-form note shown above the slider, e.g. "Applies live to the
   * running session" on the live page vs. the longer copy on the
   * detail page.
   */
  helperText?: string
}

/**
 * Slider + Save control bound to `PATCH /schedules/{id}/config`. That
 * endpoint is the only one that propagates the new threshold to a
 * running SessionPipeline (see backend update_schedule_config — it calls
 * `pipeline.update_early_leave_timeout()` when a session is active).
 *
 * The component is intentionally dumb about pipeline state: the backend
 * decides whether the change is mid-session or persistence-only, and
 * either way the operator sees the same Save → toast flow.
 */
export function EarlyLeaveTimeoutControl({
  scheduleId,
  currentMinutes,
  inline = false,
  onSaved,
  helperText,
}: Props) {
  const initial = currentMinutes ?? DEFAULT_MINUTES
  const [value, setValue] = useState(initial)
  const updateConfig = useUpdateScheduleConfig()

  // Keep the slider in sync with the persisted value when it changes
  // externally (e.g. another admin saved while this popover was open
  // and a refetch came back).
  useEffect(() => {
    setValue(currentMinutes ?? DEFAULT_MINUTES)
  }, [currentMinutes])

  const isDirty = value !== initial
  const usingDefault = currentMinutes == null

  const handleSave = async () => {
    try {
      await updateConfig.mutateAsync({
        id: scheduleId,
        data: { early_leave_timeout_minutes: value },
      })
      toast.success(`Early-leave threshold set to ${value} min`)
      onSaved?.()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      const msg =
        typeof detail === 'string'
          ? detail
          : err instanceof Error
            ? err.message
            : 'Failed to update threshold'
      toast.error(msg)
    }
  }

  const body = (
    <div className="space-y-3">
      {helperText && (
        <p className="text-xs text-muted-foreground">{helperText}</p>
      )}

      <div className="flex items-baseline justify-between">
        <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Threshold
        </span>
        <span className="text-2xl font-semibold tabular-nums leading-none">
          {value}
          <span className="ml-1 text-xs font-normal text-muted-foreground">min</span>
        </span>
      </div>

      <Slider
        value={[value]}
        min={MIN_MINUTES}
        max={MAX_MINUTES}
        step={1}
        onValueChange={(v) => setValue(v[0] ?? DEFAULT_MINUTES)}
        aria-label="Early-leave timeout in minutes"
      />

      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
        <span>{MIN_MINUTES} min</span>
        <span className="text-center">
          {usingDefault && !isDirty
            ? `System default · ${DEFAULT_MINUTES} min`
            : isDirty
              ? `Unsaved change`
              : `Saved · ${value} min`}
        </span>
        <span>{MAX_MINUTES} min</span>
      </div>

      <div className="flex justify-end pt-1">
        <Button
          size="sm"
          onClick={handleSave}
          disabled={!isDirty || updateConfig.isPending}
          className="gap-2"
        >
          {updateConfig.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Save className="h-3.5 w-3.5" />
          )}
          Save
        </Button>
      </div>
    </div>
  )

  if (inline) return body

  return (
    <div className="space-y-3 rounded-md border bg-card p-4">
      <div className="flex items-start gap-2">
        <Timer className="mt-0.5 h-4 w-4 text-muted-foreground" />
        <div className="space-y-0.5">
          <div className="text-sm font-medium">Early-leave threshold</div>
          <p className="text-xs text-muted-foreground">
            How long a recognised student can be missing from the room before
            they're flagged as early leave.
          </p>
        </div>
      </div>
      {body}
    </div>
  )
}
