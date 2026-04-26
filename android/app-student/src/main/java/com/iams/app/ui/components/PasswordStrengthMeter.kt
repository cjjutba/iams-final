package com.iams.app.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Cancel
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.RadioButtonUnchecked
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.LateFg
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary
import com.iams.app.ui.utils.PasswordEvaluation
import com.iams.app.ui.utils.PasswordStrength

/**
 * Real-time password feedback: strength meter + rule checklist.
 * Render this directly below the password [IAMSTextField].
 */
@Composable
fun PasswordStrengthMeter(
    evaluation: PasswordEvaluation,
    modifier: Modifier = Modifier,
    showChecklist: Boolean = true,
) {
    val strengthColor = when (evaluation.strength) {
        PasswordStrength.EMPTY -> Border
        PasswordStrength.WEAK -> AbsentFg
        PasswordStrength.FAIR -> LateFg
        PasswordStrength.GOOD -> LateFg
        PasswordStrength.STRONG -> PresentFg
    }
    val strengthLabel = when (evaluation.strength) {
        PasswordStrength.EMPTY -> ""
        PasswordStrength.WEAK -> "Weak"
        PasswordStrength.FAIR -> "Fair"
        PasswordStrength.GOOD -> "Good"
        PasswordStrength.STRONG -> "Strong"
    }
    val progressTarget = when (evaluation.strength) {
        PasswordStrength.EMPTY -> 0f
        PasswordStrength.WEAK -> 0.25f
        PasswordStrength.FAIR -> 0.5f
        PasswordStrength.GOOD -> 0.75f
        PasswordStrength.STRONG -> 1f
    }
    val animatedProgress by animateFloatAsState(
        targetValue = progressTarget,
        label = "passwordStrengthProgress",
    )
    val animatedStrengthColor by animateColorAsState(
        targetValue = strengthColor,
        label = "passwordStrengthColor",
    )

    Column(modifier = modifier.fillMaxWidth()) {
        // Strength bar
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(6.dp)
                    .clip(RoundedCornerShape(50))
                    .background(Border)
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxHeight()
                        .fillMaxWidth(animatedProgress)
                        .clip(RoundedCornerShape(50))
                        .background(animatedStrengthColor)
                )
            }
            if (strengthLabel.isNotEmpty()) {
                Spacer(modifier = Modifier.width(12.dp))
                Text(
                    text = strengthLabel,
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = animatedStrengthColor,
                )
            }
        }

        if (evaluation.hasWhitespace) {
            Spacer(modifier = Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Outlined.Cancel,
                    contentDescription = null,
                    modifier = Modifier.size(14.dp),
                    tint = AbsentFg,
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = "Password cannot contain spaces",
                    style = MaterialTheme.typography.bodySmall,
                    color = AbsentFg,
                )
            }
        }

        if (showChecklist) {
            Spacer(modifier = Modifier.height(10.dp))
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                evaluation.rules.forEach { rule ->
                    RuleRow(
                        label = rule.label,
                        satisfied = rule.satisfied,
                        isPristine = evaluation.strength == PasswordStrength.EMPTY,
                    )
                }
            }
        }
    }
}

@Composable
private fun RuleRow(
    label: String,
    satisfied: Boolean,
    isPristine: Boolean,
) {
    val color = when {
        isPristine -> TextTertiary
        satisfied -> PresentFg
        else -> TextSecondary
    }
    val icon = when {
        isPristine -> Icons.Outlined.RadioButtonUnchecked
        satisfied -> Icons.Outlined.CheckCircle
        else -> Icons.Outlined.RadioButtonUnchecked
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(
            imageVector = icon,
            contentDescription = if (satisfied) "Satisfied" else "Not yet satisfied",
            modifier = Modifier.size(14.dp),
            tint = color,
        )
        Spacer(modifier = Modifier.width(6.dp))
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = color,
        )
    }
}

/**
 * Inline match indicator to pair with the confirm-password field.
 * Shows nothing when [confirmPassword] is empty.
 */
@Composable
fun PasswordMatchIndicator(
    password: String,
    confirmPassword: String,
    modifier: Modifier = Modifier,
) {
    if (confirmPassword.isEmpty()) return
    val matches = password == confirmPassword && password.isNotEmpty()
    val color: Color = if (matches) PresentFg else AbsentFg
    val icon = if (matches) Icons.Outlined.CheckCircle else Icons.Outlined.Cancel
    val label = if (matches) "Passwords match" else "Passwords do not match"
    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            modifier = Modifier.size(14.dp),
            tint = color,
        )
        Spacer(modifier = Modifier.width(6.dp))
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = color,
        )
    }
}
