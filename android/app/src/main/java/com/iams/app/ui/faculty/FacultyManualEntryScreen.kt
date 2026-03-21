package com.iams.app.ui.faculty

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSButtonSize
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.IAMSHeader
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Background
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.IAMSThemeTokens
import com.iams.app.ui.theme.InputBackground
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

@Composable
fun FacultyManualEntryScreen(
    navController: NavController,
    scheduleId: String,
    viewModel: FacultyManualEntryViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val spacing = IAMSThemeTokens.spacing
    val radius = IAMSThemeTokens.radius

    var showSuccessDialog by remember { mutableStateOf(false) }
    var showErrorDialog by remember { mutableStateOf<String?>(null) }

    // Success dialog
    if (showSuccessDialog) {
        AlertDialog(
            onDismissRequest = { showSuccessDialog = false },
            title = { Text("Success") },
            text = { Text("Attendance recorded successfully") },
            confirmButton = {
                TextButton(onClick = {
                    showSuccessDialog = false
                    navController.popBackStack()
                }) {
                    Text("Done")
                }
            },
            dismissButton = {
                TextButton(onClick = {
                    showSuccessDialog = false
                    viewModel.resetForm()
                }) {
                    Text("Add Another")
                }
            }
        )
    }

    // Error dialog
    showErrorDialog?.let { errorMsg ->
        AlertDialog(
            onDismissRequest = { showErrorDialog = null },
            title = { Text("Error") },
            text = { Text(errorMsg) },
            confirmButton = {
                TextButton(onClick = { showErrorDialog = null }) {
                    Text("OK")
                }
            }
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
    ) {
        IAMSHeader(
            title = "Manual Entry",
            onBack = { navController.popBackStack() }
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(spacing.screenPadding)
        ) {
            // Description
            Text(
                text = "Manually record attendance for a student. Enter their student ID and select the appropriate status.",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary,
                lineHeight = MaterialTheme.typography.bodySmall.lineHeight
            )

            Spacer(modifier = Modifier.height(spacing.xxl))

            // Student ID field
            Text(
                text = "Student ID",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                color = Primary
            )
            Spacer(modifier = Modifier.height(spacing.sm))
            BasicTextField(
                value = uiState.studentId,
                onValueChange = { viewModel.updateStudentId(it) },
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(radius.mdShape)
                    .background(InputBackground)
                    .border(
                        width = 1.dp,
                        color = if (uiState.studentIdError != null) AbsentFg else Border,
                        shape = radius.mdShape
                    )
                    .padding(horizontal = spacing.lg, vertical = spacing.md),
                textStyle = MaterialTheme.typography.bodyLarge.copy(color = Primary),
                singleLine = true,
                cursorBrush = SolidColor(Primary),
                keyboardOptions = KeyboardOptions(
                    capitalization = KeyboardCapitalization.Characters
                ),
                decorationBox = { innerTextField ->
                    Box {
                        if (uiState.studentId.isEmpty()) {
                            Text(
                                text = "e.g. 21-A-012345",
                                style = MaterialTheme.typography.bodyLarge,
                                color = TextTertiary
                            )
                        }
                        innerTextField()
                    }
                }
            )
            if (uiState.studentIdError != null) {
                Spacer(modifier = Modifier.height(spacing.xs))
                Text(
                    text = uiState.studentIdError!!,
                    style = MaterialTheme.typography.labelSmall,
                    color = AbsentFg
                )
            }

            Spacer(modifier = Modifier.height(spacing.lg))

            // Status selection
            Text(
                text = "Status",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                color = Primary
            )
            Spacer(modifier = Modifier.height(spacing.sm))

            val statusOptions = listOf(
                "present" to "Present",
                "late" to "Late",
                "absent" to "Absent",
            )

            Column {
                statusOptions.forEach { (value, label) ->
                    val isSelected = uiState.selectedStatus == value
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(radius.mdShape)
                            .border(
                                width = 1.dp,
                                color = if (isSelected) Primary else Border,
                                shape = radius.mdShape
                            )
                            .background(if (isSelected) Primary.copy(alpha = 0.05f) else Background)
                            .clickable { viewModel.updateStatus(value) }
                            .padding(horizontal = spacing.lg, vertical = spacing.md),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = label,
                            style = MaterialTheme.typography.bodyMedium,
                            color = if (isSelected) Primary else TextSecondary,
                            fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
                            modifier = Modifier.weight(1f)
                        )
                        if (isSelected) {
                            Icon(
                                Icons.Default.Check,
                                contentDescription = "Selected",
                                modifier = Modifier.size(20.dp),
                                tint = Primary
                            )
                        }
                    }
                    if (value != statusOptions.last().first) {
                        Spacer(modifier = Modifier.height(spacing.sm))
                    }
                }
            }

            Spacer(modifier = Modifier.height(spacing.lg))

            // Remarks field
            Text(
                text = "Remarks",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                color = Primary
            )
            Spacer(modifier = Modifier.height(spacing.sm))
            BasicTextField(
                value = uiState.remarks,
                onValueChange = { viewModel.updateRemarks(it) },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(88.dp)
                    .clip(radius.mdShape)
                    .background(InputBackground)
                    .border(1.dp, Border, radius.mdShape)
                    .padding(horizontal = spacing.lg, vertical = spacing.md),
                textStyle = MaterialTheme.typography.bodyLarge.copy(color = Primary),
                cursorBrush = SolidColor(Primary),
                decorationBox = { innerTextField ->
                    Box {
                        if (uiState.remarks.isEmpty()) {
                            Text(
                                text = "Optional remarks (e.g., reason for manual entry)",
                                style = MaterialTheme.typography.bodyLarge,
                                color = TextTertiary
                            )
                        }
                        innerTextField()
                    }
                }
            )

            Spacer(modifier = Modifier.height(spacing.xxl))

            // Submit button
            IAMSButton(
                text = "Mark Attendance",
                onClick = {
                    viewModel.submit(
                        scheduleId = scheduleId,
                        onSuccess = { showSuccessDialog = true },
                        onError = { showErrorDialog = it }
                    )
                },
                isLoading = uiState.isSubmitting,
                enabled = !uiState.isSubmitting,
                size = IAMSButtonSize.LG
            )
        }
    }
}
