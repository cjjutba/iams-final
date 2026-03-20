package com.iams.app.ui.auth

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckBox
import androidx.compose.material.icons.filled.CheckBoxOutlineBlank
import androidx.compose.material.icons.filled.Face
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.iams.app.ui.components.AuthLayout
import com.iams.app.ui.components.IAMSButton
import com.iams.app.ui.components.IAMSCard
import com.iams.app.ui.components.LocalToastState
import com.iams.app.ui.components.ToastType
import com.iams.app.ui.navigation.Routes
import com.iams.app.ui.theme.AbsentFg
import com.iams.app.ui.theme.Border
import com.iams.app.ui.theme.PresentFg
import com.iams.app.ui.theme.Primary
import com.iams.app.ui.theme.Secondary
import com.iams.app.ui.theme.TextSecondary
import com.iams.app.ui.theme.TextTertiary

@Composable
fun RegisterReviewScreen(
    navController: NavController,
    viewModel: RegistrationViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val toastState = LocalToastState.current
    val hasFaces = uiState.capturedFaces.isNotEmpty()
    var isAgreed by remember { mutableStateOf(false) }

    // Toast on upload error
    LaunchedEffect(uiState.uploadError) {
        uiState.uploadError?.let {
            toastState.showToast(it, ToastType.ERROR)
            viewModel.clearUploadError()
        }
    }

    // Toast + navigate on successful upload
    LaunchedEffect(uiState.uploadSuccess) {
        if (uiState.uploadSuccess) {
            toastState.showToast("Face registration complete!", ToastType.SUCCESS)
            navController.navigate(Routes.LOGIN) {
                popUpTo(Routes.LOGIN) { inclusive = true }
            }
        }
    }

    AuthLayout(
        showBack = true,
        title = "Create Account",
        subtitle = "Step 4 of 4 - Review your information",
        onBack = { navController.popBackStack() }
    ) {
        // Progress section
        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Step 4 of 4",
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary
        )

        Spacer(modifier = Modifier.height(8.dp))

        LinearProgressIndicator(
            progress = { 1f },
            modifier = Modifier
                .fillMaxWidth()
                .height(6.dp)
                .clip(RoundedCornerShape(50)),
            color = Primary,
            trackColor = Border,
        )

        Spacer(modifier = Modifier.height(20.dp))

        // Student info card
        IAMSCard {
            Text(
                text = "Student Information",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onBackground
            )

            Spacer(modifier = Modifier.height(16.dp))

            ReviewInfoRow(
                label = "Name",
                value = "${uiState.firstName} ${uiState.lastName}".trim()
                    .ifEmpty { "Completed in Step 1" }
            )

            Spacer(modifier = Modifier.height(12.dp))

            ReviewInfoRow(
                label = "Student ID",
                value = uiState.studentId.ifEmpty { "Completed in Step 1" }
            )

            Spacer(modifier = Modifier.height(12.dp))

            ReviewInfoRow(
                label = "Email",
                value = uiState.registeredEmail.ifEmpty { "Completed in Step 2" }
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Face registration card
        IAMSCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Default.Face,
                    contentDescription = "Face",
                    modifier = Modifier.size(20.dp),
                    tint = if (hasFaces) PresentFg else AbsentFg
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "Face Registration",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onBackground
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            if (hasFaces) {
                Text(
                    text = "${uiState.capturedFaces.size} face photo(s) captured",
                    style = MaterialTheme.typography.bodyMedium,
                    color = PresentFg
                )

                Spacer(modifier = Modifier.height(12.dp))

                // Face image grid
                LazyVerticalGrid(
                    columns = GridCells.Fixed(3),
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(
                            ((uiState.capturedFaces.size + 2) / 3 * 110).dp
                        ),
                    contentPadding = PaddingValues(4.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    userScrollEnabled = false
                ) {
                    itemsIndexed(uiState.capturedFaces) { index, bitmap ->
                        FaceGridItem(bitmap = bitmap, index = index)
                    }
                }
            } else {
                // Warning badge
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(Secondary, RoundedCornerShape(10.dp))
                        .padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        Icons.Default.Warning,
                        contentDescription = "Warning",
                        modifier = Modifier.size(16.dp),
                        tint = AbsentFg
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Face registration was skipped. You can register your face later from your profile.",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextSecondary
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        // Terms checkbox
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(
                    interactionSource = remember { MutableInteractionSource() },
                    indication = null,
                    onClick = { isAgreed = !isAgreed }
                ),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = if (isAgreed) Icons.Filled.CheckBox else Icons.Filled.CheckBoxOutlineBlank,
                contentDescription = if (isAgreed) "Agreed" else "Not agreed",
                modifier = Modifier.size(24.dp),
                tint = if (isAgreed) Primary else TextSecondary
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = "I agree to the Terms of Service and Privacy Policy",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }

        Spacer(modifier = Modifier.height(8.dp))

        Spacer(modifier = Modifier.height(24.dp))

        // Submit button
        IAMSButton(
            text = if (hasFaces) "Create Account" else "Create Account",
            onClick = {
                if (hasFaces) {
                    viewModel.uploadFaceImages()
                } else {
                    // No faces captured -- go directly to login
                    navController.navigate(Routes.LOGIN) {
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                }
            },
            enabled = !uiState.isUploading && isAgreed,
            isLoading = uiState.isUploading
        )
    }
}

@Composable
private fun ReviewInfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = TextTertiary
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.onBackground
        )
    }
}

@Composable
private fun FaceGridItem(bitmap: Bitmap, index: Int) {
    Image(
        bitmap = bitmap.asImageBitmap(),
        contentDescription = "Face photo ${index + 1}",
        modifier = Modifier
            .size(100.dp)
            .clip(RoundedCornerShape(10.dp))
            .border(
                1.dp,
                Border,
                RoundedCornerShape(10.dp)
            )
    )
}
