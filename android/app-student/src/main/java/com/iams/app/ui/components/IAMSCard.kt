package com.iams.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens

@Composable
fun IAMSCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit
) {
    val radius = IAMSThemeTokens.radius
    val spacing = IAMSThemeTokens.spacing

    Surface(
        modifier = modifier
            .fillMaxWidth()
            .then(
                if (onClick != null) Modifier.clickable(onClick = onClick)
                else Modifier
            ),
        shape = radius.cardShape,
        color = Background,
        border = BorderStroke(1.dp, Border),
        shadowElevation = 0.dp,
    ) {
        Column(
            modifier = Modifier.padding(spacing.cardPadding),
            content = content
        )
    }
}
