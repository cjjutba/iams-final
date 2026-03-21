package com.iams.app.ui.components

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.Secondary

@Composable
fun SkeletonBox(
    width: Dp = Dp.Unspecified,
    height: Dp = 16.dp,
    cornerRadius: Dp = 4.dp,
    modifier: Modifier = Modifier,
) {
    val transition = rememberInfiniteTransition(label = "shimmer")
    val translateAnim by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1000f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1200, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "shimmer",
    )

    val shimmerBrush = Brush.linearGradient(
        colors = listOf(Secondary, Border, Secondary),
        start = Offset(translateAnim - 500f, 0f),
        end = Offset(translateAnim, 0f),
    )

    val boxModifier = modifier
        .then(if (width != Dp.Unspecified) Modifier.width(width) else Modifier.fillMaxWidth())
        .height(height)
        .clip(RoundedCornerShape(cornerRadius))
        .background(shimmerBrush)

    Box(modifier = boxModifier)
}

@Composable
fun TextSkeleton(
    width: Dp = 120.dp,
    height: Dp = 14.dp,
    modifier: Modifier = Modifier,
) {
    SkeletonBox(width = width, height = height, cornerRadius = 4.dp, modifier = modifier)
}

@Composable
fun CardSkeleton(
    modifier: Modifier = Modifier,
) {
    IAMSCard(modifier = modifier) {
        SkeletonBox(width = 100.dp, height = 12.dp)
        Spacer(modifier = Modifier.height(8.dp))
        SkeletonBox(height = 18.dp)
        Spacer(modifier = Modifier.height(8.dp))
        SkeletonBox(width = 180.dp, height = 14.dp)
    }
}

@Composable
fun ProfileSkeleton(
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.fillMaxWidth()) {
        Row {
            SkeletonBox(width = 80.dp, height = 80.dp, cornerRadius = 40.dp)
        }
        Spacer(modifier = Modifier.height(16.dp))
        SkeletonBox(width = 160.dp, height = 24.dp)
        Spacer(modifier = Modifier.height(8.dp))
        SkeletonBox(width = 100.dp, height = 16.dp)
    }
}
