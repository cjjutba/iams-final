package com.iams.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.BorderDark
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.InputBackground
import com.iams.app.ui.theme.TextPrimary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

@Composable
fun IAMSTextField(
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    label: String? = null,
    placeholder: String? = null,
    error: String? = null,
    enabled: Boolean = true,
    singleLine: Boolean = true,
    isPassword: Boolean = false,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
    keyboardActions: KeyboardActions = KeyboardActions.Default,
    leadingIcon: @Composable (() -> Unit)? = null,
    trailingIcon: @Composable (() -> Unit)? = null,
    maxLength: Int? = null,
    supportingText: String? = null,
) {
    val radius = IAMSThemeTokens.radius
    val layout = IAMSThemeTokens.layout
    var isFocused by remember { mutableStateOf(false) }
    var passwordVisible by remember { mutableStateOf(false) }

    val borderColor = when {
        error != null -> AbsentFg
        isFocused -> BorderDark
        else -> Border
    }

    val visualTransformation = when {
        isPassword && !passwordVisible -> PasswordVisualTransformation()
        else -> VisualTransformation.None
    }

    Column(modifier = modifier.fillMaxWidth()) {
        // Label
        if (label != null) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium,
                color = TextSecondary,
            )
            Spacer(modifier = Modifier.height(8.dp))
        }

        // Input field
        BasicTextField(
            value = value,
            onValueChange = { newValue ->
                if (maxLength != null) {
                    if (newValue.length <= maxLength) onValueChange(newValue)
                } else {
                    onValueChange(newValue)
                }
            },
            modifier = Modifier
                .fillMaxWidth()
                .height(layout.inputHeightMd)
                .clip(radius.mdShape)
                .background(InputBackground)
                .border(1.dp, borderColor, radius.mdShape)
                .onFocusChanged { isFocused = it.isFocused },
            enabled = enabled,
            singleLine = singleLine,
            textStyle = MaterialTheme.typography.bodyLarge.copy(color = TextPrimary),
            cursorBrush = SolidColor(TextPrimary),
            keyboardOptions = keyboardOptions,
            keyboardActions = keyboardActions,
            visualTransformation = visualTransformation,
            decorationBox = { innerTextField ->
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp),
                    contentAlignment = Alignment.CenterStart
                ) {
                    // Leading icon
                    if (leadingIcon != null) {
                        Box(modifier = Modifier.align(Alignment.CenterStart)) {
                            leadingIcon()
                        }
                    }

                    // Placeholder
                    if (value.isEmpty() && placeholder != null) {
                        Text(
                            text = placeholder,
                            style = MaterialTheme.typography.bodyLarge,
                            color = TextTertiary,
                            modifier = if (leadingIcon != null) {
                                Modifier.padding(start = 28.dp)
                            } else Modifier
                        )
                    }

                    // Text field
                    Box(
                        modifier = if (leadingIcon != null) {
                            Modifier.padding(start = 28.dp)
                        } else Modifier
                    ) {
                        innerTextField()
                    }

                    // Trailing icon / password toggle
                    if (isPassword) {
                        IconButton(
                            onClick = { passwordVisible = !passwordVisible },
                            modifier = Modifier.align(Alignment.CenterEnd)
                        ) {
                            Icon(
                                imageVector = if (passwordVisible) {
                                    Icons.Outlined.VisibilityOff
                                } else {
                                    Icons.Outlined.Visibility
                                },
                                contentDescription = if (passwordVisible) "Hide" else "Show",
                                tint = TextTertiary
                            )
                        }
                    } else if (trailingIcon != null) {
                        Box(modifier = Modifier.align(Alignment.CenterEnd)) {
                            trailingIcon()
                        }
                    }
                }
            }
        )

        // Error message
        if (error != null) {
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = error,
                style = MaterialTheme.typography.bodySmall,
                color = AbsentFg,
            )
        }

        // Supporting text (shown when no error)
        if (error == null && supportingText != null) {
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = supportingText,
                style = MaterialTheme.typography.bodySmall,
                color = TextTertiary,
            )
        }
    }
}
