package com.iams.app.ui.utils

import com.iams.app.ui.components.AttendanceStatus

/**
 * Single source of truth for mapping raw backend attendance status strings
 * (`present` / `late` / `absent` / `early_leave` / `excused`) to the
 * `AttendanceStatus` enum used by `IAMSBadge` and all student screens.
 *
 * Replaces three separate per-screen `parseStatus` / `parseAttendanceStatus`
 * implementations that previously collapsed every unknown string (including
 * `excused`) to `ABSENT`.
 *
 * Unknown values fall back to `ABSENT` but the caller is expected to treat
 * this as a bug signal, not a silent default.
 */
fun parseAttendanceStatus(raw: String?): AttendanceStatus {
    if (raw.isNullOrBlank()) return AttendanceStatus.ABSENT
    return when (raw.trim().lowercase()) {
        "present" -> AttendanceStatus.PRESENT
        "late" -> AttendanceStatus.LATE
        "absent" -> AttendanceStatus.ABSENT
        "early_leave", "early-leave", "earlyleave" -> AttendanceStatus.EARLY_LEAVE
        "excused" -> AttendanceStatus.EXCUSED
        else -> AttendanceStatus.ABSENT
    }
}
