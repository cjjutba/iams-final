package com.iams.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.iams.app.ui.theme.AbsentBg
import com.iams.app.ui.theme.AbsentBorder
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.EarlyLeaveBg
import com.iams.app.ui.theme.EarlyLeaveBorder
import com.iams.app.ui.theme.EarlyLeaveFg
import com.iams.app.ui.theme.ExcusedBg
import com.iams.app.ui.theme.ExcusedBorder
import com.iams.app.ui.theme.ExcusedFg
import com.iams.app.ui.theme.LateBg
import com.iams.app.ui.theme.LateBorder
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.PresentBg
import com.iams.app.ui.theme.PresentBorder
import com.iams.app.ui.theme.PresentFg

enum class AttendanceStatus { PRESENT, LATE, ABSENT, EARLY_LEAVE, EXCUSED }

data class StatusColors(
    val bg: Color,
    val fg: Color,
    val border: Color,
)

fun attendanceStatusColors(status: AttendanceStatus): StatusColors = when (status) {
    AttendanceStatus.PRESENT -> StatusColors(PresentBg, PresentFg, PresentBorder)
    AttendanceStatus.LATE -> StatusColors(LateBg, LateFg, LateBorder)
    AttendanceStatus.ABSENT -> StatusColors(AbsentBg, AbsentFg, AbsentBorder)
    AttendanceStatus.EARLY_LEAVE -> StatusColors(EarlyLeaveBg, EarlyLeaveFg, EarlyLeaveBorder)
    AttendanceStatus.EXCUSED -> StatusColors(ExcusedBg, ExcusedFg, ExcusedBorder)
}

fun attendanceStatusLabel(status: AttendanceStatus): String = when (status) {
    AttendanceStatus.PRESENT -> "Present"
    AttendanceStatus.LATE -> "Late"
    AttendanceStatus.ABSENT -> "Absent"
    AttendanceStatus.EARLY_LEAVE -> "Early Leave"
    AttendanceStatus.EXCUSED -> "Excused"
}

@Composable
fun IAMSBadge(
    status: AttendanceStatus,
    modifier: Modifier = Modifier,
) {
    val colors = attendanceStatusColors(status)
    val pillShape = RoundedCornerShape(9999.dp)

    Box(
        modifier = modifier
            .clip(pillShape)
            .background(colors.bg)
            .border(1.dp, colors.border, pillShape)
            .padding(horizontal = 10.dp, vertical = 4.dp)
    ) {
        Text(
            text = attendanceStatusLabel(status),
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.SemiBold,
            color = colors.fg,
        )
    }
}
