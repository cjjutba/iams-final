package com.iams.app.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
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
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
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

enum class ToastType {
    SUCCESS, ERROR, WARNING, INFO
}

data class ToastData(
    val message: String,
    val type: ToastType,
    val duration: Long = 3000L,
)

class ToastState {
    val currentToast: MutableState<ToastData?> = mutableStateOf(null)

    fun showToast(
        message: String,
        type: ToastType = ToastType.INFO,
        duration: Long = 3000L,
    ) {
        currentToast.value = ToastData(message, type, duration)
    }

    fun dismiss() {
        currentToast.value = null
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
    val toast = toastState.currentToast.value

    LaunchedEffect(toast) {
        if (toast != null) {
            delay(toast.duration)
            toastState.dismiss()
        }
    }

    Box(
        modifier = modifier.fillMaxSize(),
        contentAlignment = Alignment.TopCenter,
    ) {
        AnimatedVisibility(
            visible = toast != null,
            enter = slideInVertically(initialOffsetY = { -it }) + fadeIn(),
            exit = slideOutVertically(targetOffsetY = { -it }) + fadeOut(),
        ) {
            toast?.let {
                ToastContent(
                    data = it,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 48.dp),
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
        Text(
            text = data.message,
            style = MaterialTheme.typography.bodyMedium,
            color = fg,
        )
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
