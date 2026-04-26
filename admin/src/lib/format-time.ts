/**
 * format-time — single source of truth for timestamp display formats.
 *
 * Why this exists
 * ---------------
 * Before this module existed, the admin had at least 6 different
 * timestamp formats scattered across components: ``MMM d, h:mm:ss a``,
 * ``HH:mm:ss``, ``EEE MMM d, yyyy · h:mm:ss.SSS a``, plain
 * ``toLocaleString()``, ``formatDistanceToNow``, etc. An operator
 * scrolling between System Activity, the Recent Detections panel, and
 * the Recognition table couldn't visually correlate "this event here"
 * with "the same event there" because the formats didn't match.
 *
 * Pick the right helper for your display, not a free-form string.
 *
 * Display vocabulary
 * ------------------
 * - ``formatTimestamp`` — log/feed/table rows. 24h, no year.
 *   "Apr 25 17:38:42"
 * - ``formatFullDatetime`` — tooltip on a row, header banner. 24h with year.
 *   "Apr 25, 2026 17:38:42"
 * - ``formatDateOnly`` — birthdates, registered dates, anywhere a clock
 *   would be noise.
 *   "Apr 25, 2026"
 * - ``formatTimeOnly`` — a single named moment inline with text (e.g.
 *   "checked in at 5:38 PM"). 12h with AM/PM reads more naturally for
 *   isolated times.
 *   "5:38 PM"
 * - ``formatTimestampWithMs`` — the audit event-detail sheet. Same
 *   shape as formatFullDatetime plus weekday + millisecond precision
 *   for forensic correlation against backend logs.
 *   "Sat Apr 25, 2026 17:38:42.123"
 *
 * All helpers accept ``Date | string | null | undefined`` and return
 * an empty string for nullish input — no need to guard at every call
 * site.
 */

import { format } from 'date-fns'

type DateInput = Date | string | number | null | undefined

function toDate(input: DateInput): Date | null {
  if (input == null || input === '') return null
  if (input instanceof Date) {
    return Number.isNaN(input.getTime()) ? null : input
  }
  const d = new Date(input)
  return Number.isNaN(d.getTime()) ? null : d
}

/**
 * Compact log/feed timestamp without year. Use for table rows, live
 * streams, and anywhere the rough date is implicit (today/yesterday).
 *
 * Format: ``MMM d HH:mm:ss`` (24h)
 * Example: "Apr 25 17:38:42"
 */
export function formatTimestamp(input: DateInput): string {
  const d = toDate(input)
  return d ? format(d, 'MMM d HH:mm:ss') : ''
}

/**
 * Full datetime including year — for hover tooltips on log rows and
 * any banner that needs to be unambiguous across years.
 *
 * Format: ``MMM d, yyyy HH:mm:ss`` (24h)
 * Example: "Apr 25, 2026 17:38:42"
 */
export function formatFullDatetime(input: DateInput): string {
  const d = toDate(input)
  return d ? format(d, 'MMM d, yyyy HH:mm:ss') : ''
}

/**
 * Date only, with year. Use for static metadata where time-of-day is
 * meaningless — birthdates, "added to registry", "registered Apr 25".
 *
 * Format: ``MMM d, yyyy``
 * Example: "Apr 25, 2026"
 */
export function formatDateOnly(input: DateInput): string {
  const d = toDate(input)
  return d ? format(d, 'MMM d, yyyy') : ''
}

/**
 * Time of day only, 12h with AM/PM. Use when the date is implicit and
 * a single named moment reads more naturally with AM/PM than 24h.
 *
 * Format: ``h:mm a``
 * Example: "5:38 PM"
 */
export function formatTimeOnly(input: DateInput): string {
  const d = toDate(input)
  return d ? format(d, 'h:mm a') : ''
}

/**
 * Detailed timestamp with weekday + millisecond precision for the
 * event-detail sheet and any other forensic surface.
 *
 * Format: ``EEE MMM d, yyyy HH:mm:ss.SSS``
 * Example: "Sat Apr 25, 2026 17:38:42.123"
 */
export function formatTimestampWithMs(input: DateInput): string {
  const d = toDate(input)
  return d ? format(d, 'EEE MMM d, yyyy HH:mm:ss.SSS') : ''
}
