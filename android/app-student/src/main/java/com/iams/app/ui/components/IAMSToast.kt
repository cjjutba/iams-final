package com.iams.app.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.iams.app.ui.theme.AbsentBg
import com.iams.app.ui.theme.AbsentBorder
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.InfoBg
import com.iams.app.ui.theme.InfoFg
import com.iams.app.ui.theme.LateBg
import com.iams.app.ui.theme.LateBorder
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.PresentBg
import com.iams.app.ui.theme.PresentBorder
import com.iams.app.ui.theme.PresentFg
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.abs

enum class ToastType {
    SUCCESS, ERROR, WARNING, INFO
}

data class ToastData(
    val message: String,
    val type: ToastType,
    val duration: Long = 3000L,
    val subtitle: String? = null,
    val id: Long = System.nanoTime(),
)

class ToastState {
    private val _queue = mutableStateListOf<ToastData>()

    val currentToast: ToastData?
        get() = _queue.firstOrNull()

    fun showToast(
        message: String,
        type: ToastType = ToastType.INFO,
        duration: Long = 3000L,
        subtitle: String? = null,
    ) {
        if (_queue.size >= MAX_QUEUE_SIZE) return
        _queue.add(ToastData(message, type, duration, subtitle))
    }

    fun dismiss() {
        if (_queue.isNotEmpty()) {
            _queue.removeAt(0)
        }
    }

    companion object {
        private const val MAX_QUEUE_SIZE = 5
    }
}

val LocalToastState = compositionLocalOf<ToastState> {
    error("No ToastState provided")
}

@Composable
fun IAMSToastHost(
    toastState: ToastState,
    modifier: Modifier = Modifier,
) {
    val toast = toastState.currentToast
    val scope = rememberCoroutineScope()

    // Auto-dismiss timer — restarts whenever currentToast changes
    LaunchedEffect(toast?.id) {
        if (toast != null) {
            delay(toast.duration)
            toastState.dismiss()
        }
    }

    // Swipe offset state
    val offsetX = remember { Animatable(0f) }
    val offsetY = remember { Animatable(0f) }

    // Reset offsets when toast changes (queue advances)
    LaunchedEffect(toast?.id) {
        offsetX.snapTo(0f)
        offsetY.snapTo(0f)
    }

    val dismissThresholdPx = with(LocalDensity.current) { 100.dp.toPx() }

    Box(
        modifier = modifier.fillMaxSize(),
        contentAlignment = Alignment.TopCenter,
    ) {
        AnimatedVisibility(
            visible = toast != null,
            enter = slideInVertically(initialOffsetY = { -it }) + fadeIn(),
            exit = slideOutVertically(targetOffsetY = { -it }) + fadeOut(),
        ) {
            toast?.let { data ->
                val maxDrag = dismissThresholdPx * 1.5f

                ToastContent(
                    data = data,
                    modifier = Modifier
                        .padding(horizontal = 16.dp, vertical = 48.dp)
                        .graphicsLayer {
                            translationX = offsetX.value
                            translationY = offsetY.value
                            val progress = maxOf(abs(offsetX.value), abs(offsetY.value)) / maxDrag
                            alpha = (1f - progress).coerceIn(0f, 1f)
                        }
                        .pointerInput(data.id) {
                            detectDragGestures(
                                onDragEnd = {
                                    val shouldDismiss =
                                        abs(offsetX.value) > dismissThresholdPx ||
                                        offsetY.value < -dismissThresholdPx
                                    if (shouldDismiss) {
                                        toastState.dismiss()
                                    } else {
                                        scope.launch {
                                            launch { offsetX.animateTo(0f) }
                                            launch { offsetY.animateTo(0f) }
                                        }
                                    }
                                },
                                onDragCancel = {
                                    scope.launch {
                                        launch { offsetX.animateTo(0f) }
                                        launch { offsetY.animateTo(0f) }
                                    }
                                },
                                onDrag = { change, dragAmount ->
                                    change.consume()
                                    scope.launch {
                                        offsetX.snapTo(offsetX.value + dragAmount.x)
                                        // Only allow upward vertical drag
                                        val newY = (offsetY.value + dragAmount.y).coerceAtMost(0f)
                                        offsetY.snapTo(newY)
                                    }
                                },
                            )
                        },
                )
            }
        }
    }
}

@Composable
private fun ToastContent(
    data: ToastData,
    modifier: Modifier = Modifier,
) {
    val (bg, fg, borderColor, icon) = toastColors(data.type)
    val shape = RoundedCornerShape(12.dp)

    val borderModifier = if (borderColor != null) {
        Modifier.border(1.dp, borderColor, shape)
    } else {
        Modifier
    }

    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(shape)
            .then(borderModifier)
            .background(bg, shape)
            .padding(horizontal = 20.dp, vertical = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            modifier = Modifier.size(20.dp),
            tint = fg,
        )
        Spacer(modifier = Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = data.message,
                style = MaterialTheme.typography.bodyMedium,
                color = fg,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            if (!data.subtitle.isNullOrBlank()) {
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = data.subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = fg.copy(alpha = 0.8f),
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

private data class ToastColors(
    val bg: Color,
    val fg: Color,
    val border: Color?,
    val icon: ImageVector,
)

private fun toastColors(type: ToastType): ToastColors = when (type) {
    ToastType.SUCCESS -> ToastColors(PresentBg, PresentFg, PresentBorder, Icons.Default.Check)
    ToastType.ERROR -> ToastColors(AbsentBg, AbsentFg, AbsentBorder, Icons.Default.Close)
    ToastType.WARNING -> ToastColors(LateBg, LateFg, LateBorder, Icons.Default.Warning)
    ToastType.INFO -> ToastColors(InfoBg, InfoFg, null, Icons.Default.Info)
}
