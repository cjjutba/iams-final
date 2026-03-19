package com.iams.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.PrimaryForeground
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.SecondaryForeground

enum class IAMSButtonVariant { PRIMARY, SECONDARY, OUTLINE, GHOST }
enum class IAMSButtonSize { SM, MD, LG }

@Composable
fun IAMSButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    variant: IAMSButtonVariant = IAMSButtonVariant.PRIMARY,
    size: IAMSButtonSize = IAMSButtonSize.MD,
    enabled: Boolean = true,
    isLoading: Boolean = false,
    fullWidth: Boolean = true,
    leadingIcon: @Composable (() -> Unit)? = null,
) {
    val layout = IAMSThemeTokens.layout
    val radius = IAMSThemeTokens.radius

    val buttonHeight = when (size) {
        IAMSButtonSize.SM -> layout.buttonHeightSm
        IAMSButtonSize.MD -> layout.buttonHeightMd
        IAMSButtonSize.LG -> layout.buttonHeightLg
    }

    val horizontalPadding = when (size) {
        IAMSButtonSize.SM -> 12.dp
        IAMSButtonSize.MD -> 16.dp
        IAMSButtonSize.LG -> 20.dp
    }

    val buttonModifier = modifier
        .height(buttonHeight)
        .then(if (fullWidth) Modifier.fillMaxWidth() else Modifier)

    val contentPadding = PaddingValues(horizontal = horizontalPadding)

    val content: @Composable () -> Unit = {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    color = when (variant) {
                        IAMSButtonVariant.PRIMARY -> PrimaryForeground
                        else -> Primary
                    },
                    strokeWidth = 2.dp
                )
            } else {
                if (leadingIcon != null) {
                    leadingIcon()
                    Spacer(modifier = Modifier.width(8.dp))
                }
                Text(
                    text = text,
                    style = MaterialTheme.typography.labelLarge
                )
            }
        }
    }

    when (variant) {
        IAMSButtonVariant.PRIMARY -> Button(
            onClick = onClick,
            modifier = buttonModifier,
            enabled = enabled && !isLoading,
            shape = radius.mdShape,
            colors = ButtonDefaults.buttonColors(
                containerColor = Primary,
                contentColor = PrimaryForeground,
                disabledContainerColor = Primary.copy(alpha = 0.5f),
                disabledContentColor = PrimaryForeground.copy(alpha = 0.5f)
            ),
            contentPadding = contentPadding,
            content = { content() }
        )

        IAMSButtonVariant.SECONDARY -> Button(
            onClick = onClick,
            modifier = buttonModifier,
            enabled = enabled && !isLoading,
            shape = radius.mdShape,
            colors = ButtonDefaults.buttonColors(
                containerColor = Secondary,
                contentColor = SecondaryForeground,
                disabledContainerColor = Secondary.copy(alpha = 0.5f),
                disabledContentColor = SecondaryForeground.copy(alpha = 0.5f)
            ),
            contentPadding = contentPadding,
            content = { content() }
        )

        IAMSButtonVariant.OUTLINE -> OutlinedButton(
            onClick = onClick,
            modifier = buttonModifier,
            enabled = enabled && !isLoading,
            shape = radius.mdShape,
            border = BorderStroke(1.dp, if (enabled) Border else Border.copy(alpha = 0.5f)),
            colors = ButtonDefaults.outlinedButtonColors(
                contentColor = Primary,
                disabledContentColor = Primary.copy(alpha = 0.5f)
            ),
            contentPadding = contentPadding,
            content = { content() }
        )

        IAMSButtonVariant.GHOST -> TextButton(
            onClick = onClick,
            modifier = buttonModifier,
            enabled = enabled && !isLoading,
            shape = radius.mdShape,
            colors = ButtonDefaults.textButtonColors(
                contentColor = Primary,
                disabledContentColor = Primary.copy(alpha = 0.5f)
            ),
            contentPadding = contentPadding,
            content = { content() }
        )
    }
}
