/**
 * Whitespace-tolerant, case-insensitive, multi-token substring matcher.
 *
 * Splits the query on whitespace and requires each token to appear
 * somewhere in the haystack. Tokens can match in any order, so users can
 * type things like "monday active eb226" and find rows whose haystack
 * contains all three tokens regardless of their position.
 *
 * Returns true on an empty/whitespace-only query so the matcher is safe
 * to use as a no-op filter when the search box is cleared.
 */
export function tokenMatches(haystack: string, query: string): boolean {
  const trimmed = query.trim()
  if (!trimmed) return true
  const tokens = trimmed.toLowerCase().split(/\s+/)
  const hay = haystack.toLowerCase()
  return tokens.every((t) => hay.includes(t))
}

/**
 * Joins a list of haystack pieces into a single search string. Drops
 * null/undefined/empty entries so callers can pass conditional values
 * without ternary noise.
 */
export function joinHaystack(parts: Array<string | number | null | undefined | false>): string {
  return parts
    .filter((p): p is string | number => p !== null && p !== undefined && p !== '' && p !== false)
    .map((p) => String(p))
    .join(' ')
}

/**
 * Format a 24-hour `HH:MM` (or `HH:MM:SS`) string into a 12-hour clock
 * string ("7:30 AM"). Used both for display and for building haystacks
 * so users can search either format. Returns an empty string for falsy
 * input.
 */
export function formatTime12h(time: string | null | undefined): string {
  if (!time) return ''
  const [hours, minutes] = time.split(':')
  const h = parseInt(hours, 10)
  if (Number.isNaN(h)) return ''
  const ampm = h >= 12 ? 'PM' : 'AM'
  const h12 = h % 12 || 12
  return `${String(h12)}:${minutes} ${ampm}`
}

/** Day-of-week names in backend order (0=Monday..6=Sunday). */
export const DAY_NAMES_MON_FIRST = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
] as const

/**
 * Format an ISO datetime string into searchable + human-readable parts.
 * Returns the original ISO, the locale date string ("Apr 25, 2026"), and
 * the time string ("12:30 PM") so a haystack covers all three. An invalid
 * or empty input returns an empty array.
 */
export function isoDateHaystackParts(iso: string | null | undefined): string[] {
  if (!iso) return []
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return [iso]
  const out: string[] = [iso]
  try {
    out.push(date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }))
    out.push(date.toLocaleDateString(undefined, { weekday: 'long' }))
    out.push(date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', hour12: true }))
  } catch {
    /* locale-format failure — fall back to ISO only */
  }
  return out
}
