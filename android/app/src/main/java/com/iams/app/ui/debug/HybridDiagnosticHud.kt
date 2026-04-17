package com.iams.app.ui.debug

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.material3.Text
import kotlin.math.abs

/**
 * Compact translucent overlay for on-screen diagnostic metrics. See
 * `docs/plans/2026-04-17-hybrid-detection/08-diagnostic-hud.md` for the full contract.
 *
 * This composable is a pure renderer — it does not own visibility state, perform network
 * calls, write files, or log. The caller (Session 06's `FacultyLiveFeedScreen`) decides
 * when to show it. The canonical wiring:
 *
 * ```
 * var hudVisible by remember { mutableStateOf(BuildConfig.DEBUG) }
 * Box(
 *     Modifier.fillMaxSize()
 *         .pointerInput(Unit) { detectTapGestures(onLongPress = { hudVisible = !hudVisible }) },
 * ) {
 *     // existing overlay stack
 *     if (hudVisible) {
 *         HybridDiagnosticHud(
 *             snapshot = hudSnapshot,
 *             modifier = Modifier.align(Alignment.TopStart),
 *         )
 *     }
 * }
 * ```
 *
 * Anti-goals from the session plan: no theme awareness, no settings toggle screen, no
 * file / network output.
 */
@Composable
fun HybridDiagnosticHud(
    snapshot: DiagnosticMetricsCollector.Snapshot,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .padding(8.dp)
            .background(Color.Black.copy(alpha = 0.6f), RoundedCornerShape(6.dp))
            .padding(horizontal = 8.dp, vertical = 4.dp),
    ) {
        MetricRow("ML Kit FPS", "%.1f".format(snapshot.mlkitFps), alert = snapshot.mlkitFps < 10f)
        MetricRow("Backend FPS", "%.1f".format(snapshot.backendFps), alert = snapshot.backendFps < 8f)
        MetricRow("Clock skew", "${snapshot.skewMs} ms", alert = abs(snapshot.skewMs) > 1_500L)
        MetricRow("RTT", "${snapshot.rttMs} ms", alert = snapshot.rttMs > 500L)
        MetricRow(
            label = "Bound/Coast/MLKit/FB",
            value = "${snapshot.boundCount}/${snapshot.coastingCount}/" +
                "${snapshot.mlkitOnlyCount}/${snapshot.fallbackCount}",
        )
        if (snapshot.lastSeqGap > 0) {
            MetricRow("Seq gap", "${snapshot.lastSeqGap}", alert = true)
        }
    }
}

@Composable
private fun MetricRow(label: String, value: String, alert: Boolean = false) {
    Row {
        Text(
            text = "$label:",
            color = Color.White.copy(alpha = 0.7f),
            fontSize = 10.sp,
        )
        Spacer(Modifier.width(4.dp))
        Text(
            text = value,
            color = if (alert) AlertRed else Color.White,
            fontSize = 10.sp,
        )
    }
}

private val AlertRed = Color(0xFFFF5252)
