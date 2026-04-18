package com.iams.app.ui.utils

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/**
 * Centralized date/time formatters shared across student screens.
 *
 * All parse helpers return `"—"` on failure (never the raw input) so the UI
 * cannot accidentally show `"2026-04-18T10:30:00+00:00"`-style strings to
 * users when backend changes a format. Callers that want to distinguish
 * missing vs unparseable should check for `null` / blank before calling.
 */
const val EM_DASH = "—"

private val ISO_INSTANT_LOCAL = DateTimeFormatter.ISO_LOCAL_DATE_TIME
private val ISO_OFFSET = DateTimeFormatter.ISO_OFFSET_DATE_TIME
private val TIME_12H = DateTimeFormatter.ofPattern("h:mm a", Locale.US)
private val DATE_FRIENDLY = DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US)
private val WEEKDAY_DATE = DateTimeFormatter.ofPattern("EEE, MMM d", Locale.US)

/**
 * Format a backend timestamp string as `3:45 PM` in device local time.
 * Accepts ISO-8601 offset (`2026-04-18T07:45:00+00:00`), naive (`2026-04-18T07:45:00`),
 * or plain time (`07:45:00`). Returns `EM_DASH` if unparseable.
 */
fun formatClockTime(raw: String?): String {
    if (raw.isNullOrBlank()) return EM_DASH
    runCatching {
        return ZonedDateTime.parse(raw, ISO_OFFSET)
            .withZoneSameInstant(ZoneId.systemDefault())
            .format(TIME_12H)
    }
    runCatching { return LocalDateTime.parse(raw, ISO_INSTANT_LOCAL).format(TIME_12H) }
    runCatching { return LocalTime.parse(raw).format(TIME_12H) }
    return EM_DASH
}

/**
 * Format an ISO date (`2026-04-18`) as `Apr 18, 2026`. Returns `EM_DASH` if unparseable.
 */
fun formatFriendlyDate(raw: String?): String {
    if (raw.isNullOrBlank()) return EM_DASH
    return runCatching { LocalDate.parse(raw).format(DATE_FRIENDLY) }.getOrDefault(EM_DASH)
}

/**
 * Format an ISO date as `Sat, Apr 18`. Returns `EM_DASH` if unparseable.
 */
fun formatWeekdayDate(raw: String?): String {
    if (raw.isNullOrBlank()) return EM_DASH
    return runCatching { LocalDate.parse(raw).format(WEEKDAY_DATE) }.getOrDefault(EM_DASH)
}

/**
 * Parse a backend timestamp into epoch millis (UTC-anchored) for comparisons.
 * Returns `null` if unparseable. Preferred over manually parsing inside ViewModels.
 */
fun parseTimestampMillis(raw: String?): Long? {
    if (raw.isNullOrBlank()) return null
    runCatching { return ZonedDateTime.parse(raw, ISO_OFFSET).toInstant().toEpochMilli() }
    runCatching {
        return LocalDateTime.parse(raw, ISO_INSTANT_LOCAL)
            .atZone(ZoneId.systemDefault())
            .toInstant()
            .toEpochMilli()
    }
    return null
}

/**
 * Parse an ISO date string into a `LocalDate`. Returns `null` if unparseable.
 */
fun parseIsoDate(raw: String?): LocalDate? {
    if (raw.isNullOrBlank()) return null
    return runCatching { LocalDate.parse(raw) }.getOrNull()
}
